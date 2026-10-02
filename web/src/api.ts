/**
 * Thin client for the local Python server (src/server.py).
 * Responses are checked at runtime because the server is a separate program;
 * a shape mismatch should read as a clear error, not as a blank screen.
 */

export interface RunResult {
  report: string;
  errors: string[];
  verdict: "PASS" | "PARTIAL" | "FAIL" | null;
  passed: boolean;
}

const SERVER_HINT = "Start it from the repo root with: python -m src.server";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

async function readJson(res: Response): Promise<Record<string, unknown>> {
  let body: unknown;
  try {
    body = await res.json();
  } catch {
    throw new Error(`The server answered ${res.status} without JSON. ${SERVER_HINT}`);
  }
  if (!isRecord(body)) throw new Error("The server sent an unexpected response.");
  if (!res.ok) {
    const message = typeof body.error === "string" ? body.error : `Request failed with ${res.status}.`;
    throw new Error(message);
  }
  return body;
}

async function request(path: string, init?: RequestInit): Promise<Record<string, unknown>> {
  let res: Response;
  try {
    res = await fetch(path, init);
  } catch {
    throw new Error(`Can't reach the crew server. ${SERVER_HINT}`);
  }
  return readJson(res);
}

/** Loads intent/current-feature.md so the editor starts from the repo's own intent. */
export async function fetchDefaultIntent(): Promise<string> {
  const body = await request("/api/intent");
  if (typeof body.intent !== "string") throw new Error("The server sent no intent text.");
  return body.intent;
}

/** Runs the four-agent crew on the given Markdown. Takes minutes and spends API credits. */
export async function runCrew(intent: string): Promise<RunResult> {
  const body = await request("/api/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ intent }),
  });
  const { report, errors, verdict, passed } = body;
  const verdictOk = verdict === null || verdict === "PASS" || verdict === "PARTIAL" || verdict === "FAIL";
  if (
    typeof report !== "string" ||
    !Array.isArray(errors) ||
    !errors.every((e): e is string => typeof e === "string") ||
    !verdictOk ||
    typeof passed !== "boolean"
  ) {
    throw new Error("The server sent a run result in an unexpected shape.");
  }
  return { report, errors, verdict, passed };
}
