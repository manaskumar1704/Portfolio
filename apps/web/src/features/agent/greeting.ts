/**
 * The opening line.
 *
 * Its own module because it is not fixture data any more: it is the one piece of
 * copy the site owns outright, shown before anyone has typed. Moving it out of
 * `lib/api` is what makes it obvious that the api layer no longer contains fake
 * answers.
 */

export const GREETING =
  "Hi. I'm Manas's agent. Ask me about his projects, resume, skills, or how to get in touch.";