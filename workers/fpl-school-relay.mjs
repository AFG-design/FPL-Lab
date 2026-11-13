// FPL School relay (FL-147): a Cloudflare Worker that lets the FPL Lab site read one team's public details and picks.
//
// FPL's API doesn't answer requests from other websites' pages (no CORS), so the site's FPL School tab can't fetch a
// team the build didn't fetch in advance. This Worker fetches those two things from FPL and hands them to the site.
// - Only two paths: /entry/{id}/ (the team) and /entry/{id}/event/{gw}/picks/ (its picks). Anything else: 404.
// - GET only. Nothing is stored or logged by this code; responses are public FPL data, cached for 60 seconds.
// - Answers the FPL Lab site's address (and a local copy on port 8000); browsers block other sites from reading it.
// Setup: docs/fpl-school-relay.md. Free Cloudflare plan; no keys or secrets.
const FPL = "https://fantasy.premierleague.com/api";
const ORIGINS = ["https://afg-design.github.io", "http://localhost:8000"];
const PATHS = [/^\/entry\/\d{1,10}\/$/, /^\/entry\/\d{1,10}\/event\/\d{1,2}\/picks\/$/];

export const allowed = path => PATHS.some(r => r.test(path));

export async function handle(request, fetchFn = fetch) {
  const origin = request.headers.get("Origin") || "";
  const cors = { "Access-Control-Allow-Origin": ORIGINS.includes(origin) ? origin : ORIGINS[0], "Vary": "Origin" };
  if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: { ...cors, "Access-Control-Allow-Methods": "GET" } });
  if (request.method !== "GET") return new Response("GET only", { status: 405, headers: cors });
  const path = new URL(request.url).pathname;
  if (!allowed(path)) return new Response("This relay only passes on a team and its picks", { status: 404, headers: cors });
  let r;
  try {
    r = await fetchFn(FPL + path, { headers: { "User-Agent": "Mozilla/5.0 fpl-lab-relay" }, cf: { cacheTtl: 60 } });
  } catch (e) {
    return new Response("FPL didn't answer", { status: 502, headers: cors });
  }
  return new Response(r.body, { status: r.status, headers: { ...cors, "Content-Type": "application/json", "Cache-Control": "public, max-age=60" } });
}

export default { fetch: request => handle(request) };
