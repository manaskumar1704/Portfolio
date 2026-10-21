/** Liveness probe. Never touches the database so Neon can scale to zero. */
export function GET() {
  return Response.json({ status: "ok" });
}
