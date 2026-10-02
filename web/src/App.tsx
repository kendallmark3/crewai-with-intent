import { useEffect, useState, type ChangeEvent } from "react";
import ReactMarkdown from "react-markdown";
import { fetchDefaultIntent, runCrew, type RunResult } from "./api";
import { CrewPipeline } from "./CrewPipeline";

type Phase =
  | { kind: "idle" }
  | { kind: "running" }
  | { kind: "done"; result: RunResult }
  | { kind: "error"; message: string };

export function App() {
  const [intent, setIntent] = useState("");
  const [defaultIntent, setDefaultIntent] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [phase, setPhase] = useState<Phase>({ kind: "idle" });
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    fetchDefaultIntent()
      .then((text) => {
        setDefaultIntent(text);
        setIntent((current) => current || text);
      })
      .catch((err: unknown) => setLoadError(err instanceof Error ? err.message : String(err)));
  }, []);

  const running = phase.kind === "running";
  const usingDefault = defaultIntent !== null && intent === defaultIntent;
  const canRun = intent.trim().length > 0 && !running;

  async function connect() {
    setPhase({ kind: "running" });
    setCopied(false);
    try {
      setPhase({ kind: "done", result: await runCrew(intent) });
    } catch (err: unknown) {
      setPhase({ kind: "error", message: err instanceof Error ? err.message : String(err) });
    }
  }

  async function loadFile(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) setIntent(await file.text());
    e.target.value = "";
  }

  async function copyReport(report: string) {
    try {
      await navigator.clipboard.writeText(report);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  }

  return (
    <div className="shell">
      <header className="masthead">
        <h1>Crew Console</h1>
        <p className="lede">
          Paste a story or feature in Markdown, then connect. Four agents reason over it, and <code>verify.py</code> checks the report.
        </p>
        <ol className="layers" aria-label="How a run works">
          <li><span className="dot human" />Human declares</li>
          <li><span className="dot agents" />Agents reason</li>
          <li><span className="dot system" />Systems verify</li>
        </ol>
      </header>

      <main className="panes">
        <section className="pane intent-pane" aria-labelledby="intent-heading">
          <div className="pane-head">
            <h2 id="intent-heading">Intent</h2>
            <span className={`source ${usingDefault ? "" : "pasted"}`}>
              {usingDefault ? "intent/current-feature.md" : "Pasted intent"}
            </span>
          </div>
          <textarea
            id="intent-input"
            value={intent}
            onChange={(e) => setIntent(e.target.value)}
            placeholder={"# Intent: …\n\n## Success Criteria\n…\n\n## Boundaries\n…"}
            spellCheck={false}
            disabled={running}
            aria-label="Intent Markdown"
          />
          {loadError && <p className="note warn">Couldn't load current-feature.md: {loadError}</p>}
          <div className="actions">
            <button className="primary" type="button" onClick={connect} disabled={!canRun}>
              {running ? "Running…" : "Connect"}
            </button>
            <label className="secondary file">
              Open .md file
              <input id="intent-file" type="file" accept=".md,.markdown,.txt,text/markdown,text/plain" onChange={loadFile} disabled={running} />
            </label>
            {defaultIntent !== null && !usingDefault && (
              <button className="link" type="button" onClick={() => setIntent(defaultIntent)} disabled={running}>
                Use current-feature.md
              </button>
            )}
          </div>
          <p className="note">Each run calls Claude several times and uses API credits. The pasted text is used for this run only; current-feature.md is not changed.</p>
        </section>

        <section className="pane report-pane" aria-labelledby="report-heading">
          <div className="pane-head">
            <h2 id="report-heading">Report</h2>
            {phase.kind === "done" && (
              <button className="link" type="button" onClick={() => copyReport(phase.result.report)}>
                {copied ? "Copied" : "Copy Markdown"}
              </button>
            )}
          </div>

          {phase.kind === "idle" && (
            <div className="empty">
              <p>The final engineering report shows up here, with the result of the verification gate above it.</p>
              <p className="muted">It's also saved to <code>output/final_report.md</code>.</p>
            </div>
          )}

          {running && <CrewPipeline />}

          {phase.kind === "error" && (
            <div className="banner fail" role="alert">
              <strong>Run didn't finish.</strong> {phase.message}
            </div>
          )}

          {phase.kind === "done" && (
            <>
              <div className={`banner ${phase.result.passed ? "pass" : "fail"}`}>
                <strong>{phase.result.passed ? "Verification passed" : "Verification failed"}</strong>
                <span className="verdict">Reviewer verdict: {phase.result.verdict ?? "none given"}</span>
                {!phase.result.passed && (
                  <ul>
                    {phase.result.errors.map((e) => <li key={e}>{e}</li>)}
                  </ul>
                )}
              </div>
              <article className="report">
                <ReactMarkdown>{phase.result.report}</ReactMarkdown>
              </article>
            </>
          )}
        </section>
      </main>
    </div>
  );
}
