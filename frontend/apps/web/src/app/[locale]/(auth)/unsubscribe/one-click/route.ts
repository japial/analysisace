import type { NextRequest } from "next/server";

import { ApiError, unsubscribeByLink } from "@/lib/api";

/**
 * RFC 8058 one-click unsubscribe (D34). Mail apps post "List-Unsubscribe=One-Click" to the
 * address in an email's List-Unsubscribe header, with no cookies and no page to show.
 */
export async function POST(request: NextRequest): Promise<Response> {
  const token = request.nextUrl.searchParams.get("t") ?? "";
  try {
    await unsubscribeByLink(token);
    return new Response(null, { status: 200, headers: { "Cache-Control": "no-store" } });
  } catch (error) {
    const status = error instanceof ApiError && error.status === 400 ? 400 : 503;
    return new Response(null, { status });
  }
}

/** Opened in a browser instead: the page that asks first, since opening a link never acts. */
export function GET(request: NextRequest): Response {
  const page = request.nextUrl.clone();
  page.pathname = page.pathname.replace(/\/one-click\/?$/, "");
  return Response.redirect(page, 303);
}
