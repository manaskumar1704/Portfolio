/** Fixed CRT scanlines + vignette, pointer-events none. */
export function CrtOverlay() {
  return (
    <div
      aria-hidden="true"
      className="pointer-events-none fixed inset-0 z-[60] mix-blend-overlay [background:repeating-linear-gradient(180deg,rgba(255,255,255,.022)_0_1px,transparent_1px_3px)]"
    >
      <div className="absolute inset-0 [background:radial-gradient(120%_90%_at_50%_30%,transparent_55%,rgba(0,0,0,.35))]" />
    </div>
  );
}
