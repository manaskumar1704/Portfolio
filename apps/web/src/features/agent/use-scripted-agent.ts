"use client";

import { useEffect, useRef, useState } from "react";
import { ask as askApi, GREETING } from "@/lib/api/chat";
import type { ChatMessage, ChatRole } from "@/lib/api/types";
import { REDUCED_MOTION_QUERY } from "@/hooks/use-reduced-motion";

const THINK_MS = 420;
const WORD_MS = 24;

/**
 * The scripted agent behind the composer: keyword replies from `lib/api`,
 * word-by-word streaming render, and the greeting on first interaction.
 *
 * Navigation is not here. That is the URL's job, driven by links in the
 * listings, the topbar and the landing shortcuts.
 */
export function useScriptedAgent() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);
  const [dismissed, setDismissed] = useState(false);
  const nextId = useRef(0);
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);

  useEffect(() => {
    const pending = timers.current;
    return () => pending.forEach(clearTimeout);
  }, []);

  const later = (fn: () => void, ms: number) => {
    timers.current.push(setTimeout(fn, ms));
  };

  const update = (id: number, patch: Partial<ChatMessage>) =>
    setMessages((prev) =>
      prev.map((m) => (m.id === id ? { ...m, ...patch } : m)),
    );

  const push = (role: ChatRole, text: string, thinking = false) => {
    const id = nextId.current++;
    setMessages((prev) => [...prev, { id, role, text, thinking }]);
    return id;
  };

  const stream = (id: number, full: string, onDone?: () => void) => {
    // Read at call time, not render: only a callback consumes this.
    if (window.matchMedia(REDUCED_MOTION_QUERY).matches) {
      update(id, { text: full, thinking: false });
      onDone?.();
      return;
    }
    const words = full.split(" ");
    let i = 0;
    const step = () => {
      i += 1;
      update(id, { text: words.slice(0, i).join(" "), thinking: false });
      if (i < words.length) later(step, WORD_MS);
      else onDone?.();
    };
    later(step, WORD_MS);
  };

  const greet = () => {
    stream(push("bot", ""), GREETING);
  };

  const dismiss = () => {
    if (dismissed) return;
    setDismissed(true);
    greet();
  };

  const send = async (raw?: string) => {
    const text = (raw ?? value).trim();
    if (!text || busy) return;
    dismiss();
    if (raw === undefined) setValue("");
    setBusy(true);
    push("user", text);
    const botId = push("bot", "", true);
    try {
      const { reply } = await askApi(text);
      later(() => stream(botId, reply, () => setBusy(false)), THINK_MS);
    } catch {
      update(botId, {
        text: "Connection failed — try again in a moment.",
        thinking: false,
      });
      setBusy(false);
    }
  };

  return {
    messages,
    value,
    busy,
    dismissed,
    onValueChange: setValue,
    send,
    dismiss,
  };
}
