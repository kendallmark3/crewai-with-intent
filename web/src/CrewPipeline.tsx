import { useEffect, useState } from "react";

const AGENTS = ["Requirements Analyst", "Solution Architect", "Developer", "Intent Reviewer"] as const;

/**
 * Shown while the crew runs. The server returns only when all four agents are done,
 * so the pulse loops through the pipeline instead of claiming which agent is active.
 */
export function CrewPipeline() {
  const [seconds, setSeconds] = useState(0);

  useEffect(() => {
    const started = Date.now();
    const id = window.setInterval(() => setSeconds(Math.floor((Date.now() - started) / 1000)), 1000);
    return () => window.clearInterval(id);
  }, []);

  const mm = Math.floor(seconds / 60);
  const ss = String(seconds % 60).padStart(2, "0");

  return (
    <div className="pipeline">
      <div className="track" aria-hidden="true">
        <div className="pulse" />
        {AGENTS.map((agent, i) => (
          <div className="station" key={agent}>
            <span className="node">{i + 1}</span>
            <span className="station-label">{agent}</span>
          </div>
        ))}
      </div>
      <p className="pipeline-status">
        <span role="status">The crew is working through your intent in order.</span>
        <span className="elapsed" aria-label={`${mm} minutes ${ss} seconds elapsed`}>{mm}:{ss}</span>
      </p>
      <p className="pipeline-hint">A run usually takes a few minutes. The report appears here when the last agent finishes.</p>
    </div>
  );
}
