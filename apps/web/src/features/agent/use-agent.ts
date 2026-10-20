"use client";

/**
 * The real agent: one turn of `POST /chat`, streamed.
 *
 * Replaces `use-scripted-agent`, which drove the keyword fixtures in
 * `lib/api/chat.ts`. The wire contract is in `lib/api/types.ts`; the transport
 * is in `lib/api/sse.ts`; frames are parsed in `lib/api/parse-sse.ts`; approval
 * is sent from `lib/api/draft-approve.ts`; the `/commands` table this hook
 * consults before streaming anything is in `lib/api/commands.ts`.
 *
 * ## States
 *
 *   idle      nothing typed, no API contact
 *   waking    Render slept; /health has not answered. NOT an error.
 *   thinking  request sent, no token yet
 *   streaming tokens arriving
 *   done      answer complete
 *   busy      429, too many questions
 *   error     anything else
 *
 * `waking` exists because Render's free tier sleeps after 15 minutes and the
 * first `/chat` would otherwise eat a cold start with nothing on screen to
 * explain it. The ping is `/health` and never `/ready`, because `/ready` opens a
 * Postgres connection and calling it on every page load would hold Neon out of
 * scale-to-zero.
 *
 * ## The token
 *
 * Held in a ref. Never state, never storage. `readToken` is handed to
 * `DraftApproval` so the value never becomes a serialisable prop. See that
 * component's docstring.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { GREETING } from "./greeting";
import { COMMANDS_HELP, resolveCommand } from "@/lib/api/commands";
import { pingHealth, streamChat } from "@/lib/api/sse";
import type { AgentStatus, ChatMessage, ChatEvent, Citation, Draft } from "@/lib/api/types";
import { REDUCED_MOTION_QUERY } from "@/hooks/use-reduced-motion";

/** What an unrecognised `/command` gets: the list of what exists, locally. */
const UNKNOWN_REPLY = `That's not a command I know.\n\n${COMMANDS_HELP}`;

export function useAgent() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [status, setStatus] = useState<AgentStatus>("idle");
  const [value, setValue] = useState("");
  const [draft, setDraft] = useState<Draft | null>(null);
  const [dismissed, setDismissed] = useState(false);

  const nextId = useRef(0);
  const inFlight = useRef<AbortController | null>(null);

  // The send capability. A ref, so it is not in React's tree, and nulled once
  // spent. See ADR 0006.
  const tokenRef = useRef<{ id: number; token: string } | null>(null);

  const readToken = useCallback(() => {
    if (!draft) return null;
    return tokenRef.current?.id === draft.id ? tokenRef.current.token : null;
  }, [draft]);

  // ── Warm on visit ─────────────────────────────────────────────────────
  //
  // Fire and forget. The result only decides whether the composer says
  // "waking up" instead of "ask me something", which is a nicety, so a failure
  // here must not surface anywhere.
  useEffect(() => {
    if (!dismissed) return;

    const controller = new AbortController();
    let alive = true;

    pingHealth(controller.signal).then(({ ok }) => {
      if (alive && !ok) setStatus((current) => (current === "idle" ? "waking" : current));
    });

    return () => {
      alive = false;
      controller.abort();
    };
  }, [dismissed]);

  // A turn in flight must not outlive the component, or a React state update
  // lands on an unmounted tree and the console fills with warnings.
  useEffect(() => () => inFlight.current?.abort(), []);

  const update = (id: number, patch: Partial<ChatMessage>) =>
    setMessages((previous) =>
      previous.map((message) => (message.id === id ? { ...message, ...patch } : message)),
    );

  const push = (role: "user" | "bot", text: string, thinking = false) => {
    const id = nextId.current++;
    setMessages((previous) => [...previous, { id, role, text, thinking }]);
    return id;
  };

  const dismiss = () => {
    if (dismissed) return;
    setDismissed(true);
    push("bot", GREETING);
    setStatus("idle");
  };

  /** Fold one SSE event into the message list. */
  const apply = (event: ChatEvent, botId: number) => {
    switch (event.kind) {
      case "delta":
        setStatus("streaming");
        setMessages((previous) =>
          previous.map((message) =>
            message.id === botId
              ? { ...message, text: message.text + event.text, thinking: false }
              : message,
          ),
        );
        break;

      case "citation":
        setMessages((previous) =>
          previous.map((message) => {
            if (message.id !== botId) return message;
            const next = dedupeCitations([
              ...(message.citations ?? []),
              { label: event.label, sourcePath: event.sourcePath },
            ]);
            return { ...message, citations: next };
          }),
        );
        break;

      case "draft":
        // The token goes straight into the ref and nowhere else.
        tokenRef.current = { id: event.id, token: event.approvalToken };
        setDraft({
          id: event.id,
          name: event.name,
          email: event.email,
          body: event.body,
          expiresAt: event.expiresAt,
        });
        break;

      case "busy":
        setStatus("busy");
        update(botId, { text: event.message, thinking: false });
        break;

      case "error":
        setStatus("error");
        update(botId, { text: event.message, thinking: false });
        break;

      case "done":
        setStatus("done");
        update(botId, { thinking: false, sourcesVerified: event.sourcesVerified });
        break;

      // `tool_call` is deliberately silent. A "searching…" line on every
      // question is noise; the citations that follow are the honest signal.
      case "tool_call":
      case "tool_result":
      case "unknown":
        break;
    }
  };

  const send = async (raw?: string) => {
    const text = (raw ?? value).trim();
    if (!text || status === "thinking" || status === "streaming") return;

    const command = resolveCommand(text);
    dismiss();
    if (raw === undefined) setValue("");

    // Commands are answered where the answer already exists: in the browser.
    // None of these reach the LLM, and so none of them can hallucinate about
    // what the site can and cannot do while it is booting up.
    if (command === "unknown") {
      push("user", text);
      push("bot", UNKNOWN_REPLY);
      setStatus("idle");
      return;
    }

    if (command?.kind === "clear") {
      setMessages([]);
      push("bot", GREETING);
      setStatus("idle");
      return;
    }

    if (command?.kind === "reply") {
      push("user", text);
      push("bot", command.message);
      setStatus("idle");
      return;
    }

    // A prompt alias shares the plain-question path. The bubble shows what is
    // actually sent (the expansion, for a command) — what the model sees is
    // what the visitor can read they asked.
    const spoken = command ? command.message : text;
    push("user", spoken);

    const reduced = window.matchMedia(REDUCED_MOTION_QUERY).matches;
    const history = messages
      .filter((message) => message.text.trim() && !message.thinking)
      .map(({ role, text: body }) => ({ role, text: body }));

    const controller = new AbortController();
    inFlight.current = controller;

    const botId = push("bot", "", !reduced);
    setStatus("thinking");

    // With reduced motion there is no staged "thinking" beat; the bubble simply
    // appears when the first token lands.
    if (reduced) update(botId, { thinking: false });

    try {
      for await (const event of streamChat({ message: spoken, history, signal: controller.signal })) {
        apply(event, botId);
      }
    } catch (error) {
      if ((error as Error)?.name !== "AbortError") {
        setStatus("error");
        update(botId, {
          text: "Could not reach the agent. Try again in a moment.",
          thinking: false,
        });
      }
    } finally {
      inFlight.current = null;
      setStatus((current) => (current === "thinking" || current === "streaming" ? "done" : current));
    }
  };

  return {
    messages,
    status,
    value,
    draft,
    dismissed,
    busy: status === "thinking" || status === "streaming",
    readToken,
    clearDraft: () => {
      tokenRef.current = null;
      setDraft(null);
    },
    onValueChange: setValue,
    send,
    dismiss,
  };
}

/** First sighting wins, so a chunk cited twice is listed once. */
function dedupeCitations(citations: Citation[]): Citation[] {
  const seen = new Set<string>();
  return citations.filter((citation) => {
    if (seen.has(citation.sourcePath)) return false;
    seen.add(citation.sourcePath);
    return true;
  });
}