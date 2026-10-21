# 0003 — Gemini primary, and the shape of a tool loop

Phase 3, revising 0001 now that a provider is chosen. Three decisions, each of
which was settled by running code against the live API rather than by reading
docs.

## Gemini `gemini-3.5-flash-lite`, Groq as the 429 fallback

Verified against the live API before writing anything: 1,048,576 input tokens,
65,536 output tokens, and a real `functionCall` step returned for a tool
declaration. It is the cheapest no-card option that does function calling
properly, and the whole demo is a streaming UI where time-to-first-token is the
product. Groq stays wired for rate-limit headroom.

Two model ids worth recording. `gemini-3.5-flash-lite` is the current name;
anything in the `gemini-2.5-*` family is deprecated and must not be used. And a
model named in a skill or a blog post is not a guarantee — the check is one
call to `GET /v1beta/models?key=$GEMINI_API_KEY`.

## A tool loop needs `previous_interaction_id`, and that is not obvious

The documented shape reads as though the whole conversation could be replayed
each leg. It cannot. Sending `user_input` + `function_call` + `function_result`
in one stateless `input` list returns `400 invalid_request`. Only a
`function_result` attached to an interaction that already recorded the call is
accepted.

So a turn is stateful: leg one creates an interaction and returns its id, and
every leg after it passes that id plus only the new results. The loop keeps the
id in a local variable for the life of one request and discards it. Nothing is
persisted, which is what 0001 promised about conversation history.

This is why the `LLMClient` interface carries `previous_interaction_id` and
`tool_results` together. The parameter looks redundant until you write the Groq
adapter, which accepts the results as ordinary messages and ignores the id
entirely. The interface has to be shaped by the *worst* provider in the set, not
the best one.

Two shape details that only fail locally, which is the good kind of failure:

- `user_input.content` is a **list of content parts**, not a bare string. A
  string fails pydantic validation before a request is made.
- `function_result.result` is likewise a list of parts.

Both are now pinned by tests, because they are exactly the kind of detail that a
future SDK bump silently changes.

## Interactions are stored, and that is the cost of the state machine

Interactions are stored by default: 55 days on paid tiers, one day on free.
`store=False` opts out — and disables `previous_interaction_id`, which is the
mechanism the tool loop is built on.

So the choice is between storing a recruiter's conversation with Google for a day
and not having a working tool loop. This project stores. The reasoning is that
the corpus is public professional information and the visitor is already talking
to a third-party model about it. If that changes, the answer is to drop the
`interactions` surface for `generateContent` with an explicit `contents` list,
which costs a second adapter and loses nothing else.

## The tool registry is the security boundary

The model picks a name from a module-level dict. It cannot invent one, and it
cannot reach a function that is not in the dict. A tool that throws returns an
error string to the model rather than raising, because a 500 mid-stream leaves
the visitor with a spinner and half an answer.

Tool arguments are validated against a Pydantic model before the handler runs.
The complaint is returned to the model in the same channel as a result, so a
model that invents a parameter can correct itself instead of failing the turn.

Two bounds worth naming: `MAX_TOOL_ITERATIONS = 4` stops the loop when a model
keeps re-calling the same tool, and `MAX_MESSAGE_CHARS = 4000` stops one request
becoming a thousand prompt tokens before any limiter runs. Both are cheap
insurance against a free tier being spent by accident.

## An in-process token bucket, and why not Redis

Render free runs one instance, so a process-local dict is the complete story.
Redis or a Postgres table would add a dependency and a second free-tier limit to
solve a problem that does not exist yet. Buckets are swept after five idle
minutes so the dict cannot grow by one entry per distinct IP forever.

**`ponytail: in-process rate counters that reset on spin-down.`** Move to a
shared store when this runs more than one instance. The refill arithmetic is
continuous rather than per-window, which matters because recruiter traffic
arrives in bursts — three questions in four seconds is a person reading a page,
not an attack.