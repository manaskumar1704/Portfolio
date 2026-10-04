import type { Contact } from "./types";

/** Mock shape matches GET /contact on the FastAPI backend. */
export async function getContact(): Promise<Contact> {
  return {
    email: "manas@example.com",
    github: "https://github.com/manas-dev",
    linkedin: "https://linkedin.com/in/manas-dev",
    note: "Placeholder links — replace with real handles before publishing. Open to GenAI / full-stack roles.",
  };
}
