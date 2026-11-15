import { ApiError, exportMe } from "@/lib/api";
import { getSessionToken } from "@/lib/session";

/** Self-service data export (FR23.4): the signed-in user's data as a JSON file. */
export async function GET(): Promise<Response> {
  const token = await getSessionToken();
  if (!token) return new Response(null, { status: 401 });
  try {
    const data = await exportMe(token);
    return new Response(JSON.stringify(data, null, 2), {
      headers: {
        "Content-Type": "application/json; charset=utf-8",
        "Content-Disposition": 'attachment; filename="analysisace-my-data.json"',
        "Cache-Control": "no-store",
      },
    });
  } catch (error) {
    const status = error instanceof ApiError ? error.status : 500;
    return new Response(null, { status });
  }
}
