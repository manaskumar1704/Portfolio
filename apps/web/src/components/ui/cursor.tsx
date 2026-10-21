/** Blinking terminal caret. */
export function Cursor() {
  return (
    <span
      aria-hidden="true"
      className="inline-block h-[1.05em] w-[0.6em] translate-y-[0.14em] animate-[blink_1.05s_steps(1)_infinite] bg-accent"
    />
  );
}
