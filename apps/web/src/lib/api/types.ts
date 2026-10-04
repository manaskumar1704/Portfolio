export type ProjectStatus = "completed" | "running" | "soon";

export type Project = {
  name: string;
  status: ProjectStatus;
  label: string;
  meta: string;
  desc: string;
  stack: string;
};

export type Contact = {
  email: string;
  github: string;
  linkedin: string;
  note: string;
};

export type ChatRole = "user" | "bot";

export type ChatMessage = {
  id: number;
  role: ChatRole;
  text: string;
  /** true while the agent shows its "thinking" indicator */
  thinking?: boolean;
};

/** Shape the real FastAPI POST /chat will return. */
export type ChatReply = {
  reply: string;
};
