import React, { useState, useEffect } from "react";
import { getTraces } from "./api";

export default function TraceViewer({ currentSessionId }) {
  const [traces, setTraces] = useState([]);
  const [filterSession, setFilterSession] = useState(currentSessionId || "");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const loadTraces = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getTraces(filterSession || null, 150);
      setTraces(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTraces();
  }, [filterSession]);

  // Aggregate Metrics
  const totalTurns = traces.length;
  const toolExecutions = traces.filter((t) => t.role === "tool").length;
  const guardrailEvents = traces.filter((t) => t.guardrail_flags).length;
  const totalLatencyMs = traces.reduce((acc, t) => acc + (t.latency_ms || 0), 0);
  const totalTokens = traces.reduce(
    (acc, t) => acc + (t.input_tokens || 0) + (t.output_tokens || 0),
    0
  );

  return (
    <div className="trace-page">
      <div style={{ display: "flex", gap: "1rem", alignItems: "center" }}>
        <input
          type="text"
          className="chat-input"
          style={{ maxWidth: "350px" }}
          placeholder="Filter by Session ID (or leave empty for all)..."
          value={filterSession}
          onChange={(e) => setFilterSession(e.target.value)}
        />
        <button className="action-btn" onClick={loadTraces} disabled={loading}>
          {loading ? "Refreshing..." : "🔄 Refresh Traces"}
        </button>
        {currentSessionId && (
          <button
            className="action-btn"
            onClick={() => setFilterSession(currentSessionId)}
          >
            Show Current Session
          </button>
        )}
      </div>

      {/* Metrics Cards */}
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-label">Logged Traces</div>
          <div className="stat-value">{totalTurns}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Tool Invocations</div>
          <div className="stat-value" style={{ color: "var(--accent-blue)" }}>
            {toolExecutions}
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Guardrail Events</div>
          <div
            className="stat-value"
            style={{ color: guardrailEvents > 0 ? "var(--accent-amber)" : "var(--accent-green)" }}
          >
            {guardrailEvents}
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Total Latency / Tokens</div>
          <div className="stat-value" style={{ fontSize: "1.2rem" }}>
            {Math.round(totalLatencyMs)}ms / {totalTokens} tk
          </div>
        </div>
      </div>

      {error && (
        <div style={{ color: "var(--accent-red)", padding: "1rem" }}>
          ⚠️ Failed to load traces: {error}
        </div>
      )}

      {/* Timeline */}
      <div className="trace-timeline">
        <h3 style={{ fontSize: "1rem", color: "var(--text-secondary)", marginBottom: "0.5rem" }}>
          Execution Step Timeline (Chronological)
        </h3>

        {traces.length === 0 && !loading && (
          <div style={{ color: "var(--text-muted)", padding: "2rem", textAlign: "center" }}>
            No trace events recorded yet for this session filter.
          </div>
        )}

        {traces.map((t) => (
          <div key={t.id} className="trace-item">
            <div className="trace-top">
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <span className={`trace-role-badge ${t.role}`}>{t.role}</span>
                <span style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>
                  Turn #{t.turn} &bull; Session: <code>{t.session_id}</code>
                </span>
              </div>
              <div className="trace-flags">
                {t.guardrail_flags && (
                  <span className="flag-pill">🛡️ {t.guardrail_flags}</span>
                )}
                {t.error && <span className="flag-pill" style={{ color: "#f87171" }}>❌ {t.error}</span>}
              </div>
            </div>

            <div className="trace-meta">
              {t.tool_name && <span>Tool: <strong>{t.tool_name}</strong></span>}
              {t.latency_ms > 0 && <span>Latency: {Math.round(t.latency_ms)}ms</span>}
              {(t.input_tokens > 0 || t.output_tokens > 0) && (
                <span>Tokens: {t.input_tokens} in / {t.output_tokens} out</span>
              )}
              {t.created_at && <span>Time: {new Date(t.created_at).toLocaleTimeString()}</span>}
            </div>

            {t.content && <div className="trace-content">{t.content}</div>}

            {t.tool_args && (
              <div>
                <span style={{ fontSize: "0.7rem", color: "var(--accent-blue)" }}>// Arguments</span>
                <pre className="trace-content">{JSON.stringify(t.tool_args, null, 2)}</pre>
              </div>
            )}

            {t.tool_result && (
              <div>
                <span style={{ fontSize: "0.7rem", color: "var(--accent-green)" }}>// Result</span>
                <pre className="trace-content">{JSON.stringify(t.tool_result, null, 2)}</pre>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
