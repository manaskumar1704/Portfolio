/**
 * The one place that reads `process.env`.
 *
 * ## Why it exists
 *
 * `NEXT_PUBLIC_API_URL` was declared in `.env.example` and read nowhere, so
 * nothing in the bundle knew where the API was. Centralising it means there is
 * exactly one line to change when the host moves.
 *
 * ## The value is inlined at build time
 *
 * Next replaces the literal `process.env.NEXT_PUBLIC_API_URL` with the build-time
 * value. Two consequences:
 *
 * - **It must be written literally.** `process.env[name]` with a variable is NOT
 *   inlined — the documented behaviour is that dynamic lookups silently resolve
 *   to undefined. Hence `API_BASE = process.env.NEXT_PUBLIC_API_URL` and no
 *   indirection anywhere downstream.
 * - **Changing it on Vercel requires a rebuild**, not just a redeploy. Setting it
 *   under the project's Production/Preview/D Development environment variables
 *   is enough; Vercel rebuilds when one changes.
 *
 * It is not a secret. The Render URL is public by nature and every browser
 * already knows it.
 */

/** The API origin, with no trailing slash. Empty when unset. */
export const API_BASE: string = stripTrailingSlash(process.env.NEXT_PUBLIC_API_URL);

function stripTrailingSlash(value: string | undefined): string {
  return (value ?? "").replace(/\/+$/, "");
}

/** True when the API origin is configured. Drives the "not deployed yet" notice. */
export const apiConfigured: boolean = API_BASE.length > 0;

/**
 * Join a path onto the base. Used by every call so no caller concatenates URLs.
 *
 * Returns the path unchanged when the base is empty, which keeps the fixtures
 * working in a checkout with no `.env.local` at all.
 */
export function apiUrl(path: string): string {
  return API_BASE ? `${API_BASE}${path}` : path;
}