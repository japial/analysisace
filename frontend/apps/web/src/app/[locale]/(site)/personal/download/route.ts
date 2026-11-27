import { requestRaw } from "@/lib/api";
import { getSessionToken } from "@/lib/session";

/**
 * Passes a file from the API to the browser: the cost and income exports (FR12.5, FR27.7), a tax statement as
 * CSV (FR13.5), a Zakat or tax statement as PDF (FR13) or a stored document (FR25.5). Only
 * these paths are allowed, and the API checks that the signed-in person may read the
 * household.
 */
const ALLOWED = [
  /^\/households\/[0-9a-f-]{36}\/costs\/export\.csv$/,
  /^\/households\/[0-9a-f-]{36}\/income\/export\.csv$/,
  /^\/households\/[0-9a-f-]{36}\/tax\/snapshots\/[0-9a-f-]{36}\/export\.csv$/,
  /^\/households\/[0-9a-f-]{36}\/(zakat|tax)\/snapshots\/[0-9a-f-]{36}\/statement\.pdf\?locale=(en|bn)$/,
  /^\/households\/[0-9a-f-]{36}\/alt-assets\/[0-9a-f-]{36}\/documents\/[0-9a-f-]{36}$/,
  // F9 (D30): a firm's CSV exports, white-label weekly report and logo.
  /^\/firms\/[0-9a-f-]{36}\/exports\/(shariah|scores)\.csv$/,
  /^\/firms\/[0-9a-f-]{36}\/reports\/weekly\.pdf\?locale=(en|bn)(&week=\d{4}-\d{2}-\d{2})?$/,
  /^\/firms\/[0-9a-f-]{36}\/logo$/,
];

export async function GET(request: Request): Promise<Response> {
  const token = await getSessionToken();
  if (!token) return new Response(null, { status: 401 });
  const path = new URL(request.url).searchParams.get("path") ?? "";
  if (!ALLOWED.some((pattern) => pattern.test(path))) return new Response(null, { status: 404 });

  const upstream = await requestRaw(path, token).catch(() => null);
  if (!upstream) return new Response(null, { status: 503 });
  if (!upstream.ok) return new Response(null, { status: upstream.status });
  return new Response(upstream.body, {
    headers: {
      "Content-Type": upstream.headers.get("Content-Type") ?? "application/octet-stream",
      "Content-Disposition": upstream.headers.get("Content-Disposition") ?? "attachment",
      "X-Content-Type-Options": "nosniff",
      "Cache-Control": "no-store",
    },
  });
}
