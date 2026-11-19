import React, { useState, useEffect } from "react";
import Chat from "./Chat";
import TraceViewer from "./TraceViewer";
import { getHealth, resetDatabase } from "./api";

function generateSessionId() {
  return "sess-" + Math.random().toString(36).substring(2, 9);
}

export default function App() {
  const [activeTab, setActiveTab] = useState("chat");
  const [sessionId, setSessionId] = useState(generateSessionId());
  const [health, setHealth] = useState(null);

  useEffect(() => {
    getHealth()
      .then(setHealth)
      .catch((err) => console.warn("Backend offline:", err));
  }, []);

  const handleNewSession = () => {
    setSessionId(generateSessionId());
  };

  const handleResetDb = async () => {
    if (window.confirm("Are you sure you want to reseed the database with 40 customers and 150 orders?")) {
      try {
        const res = await resetDatabase();
        alert(`Database reseeded! (${res.counts.orders} orders loaded)`);
        handleNewSession();
      } catch (err) {
        alert("Failed to reset database: " + err.message);
      }
    }
  };

  return (
    <div className="app-container">
      <header className="app-header">
        <div className="brand-section">
          <span className="brand-icon">🛡️</span>
          <div>
            <div className="brand-title">
              ShopAssist AI
              <span style={{ fontSize: "0.75rem", opacity: 0.7, fontWeight: 400 }}>v1.0</span>
            </div>
            <div className="brand-subtitle">
              Reliable Tool-Calling Customer Support with Built-in Guardrails
            </div>
          </div>
        </div>

        {/* Tab Switcher */}
        <div className="nav-tabs">
          <button
            className={`nav-tab ${activeTab === "chat" ? "active" : ""}`}
            onClick={() => setActiveTab("chat")}
          >
            💬 Support Chat
          </button>
          <button
            className={`nav-tab ${activeTab === "traces" ? "active" : ""}`}
            onClick={() => setActiveTab("traces")}
          >
            📊 Trace Viewer & Observability
          </button>
        </div>

        {/* Right Status & Actions */}
        <div className="header-status">
          {health && (
            <>
              <span className="status-badge online">● {health.provider}</span>
              <span className="status-badge guardrails">
                🛡️ {health.guardrails_enabled ? "Guarded" : "Baseline"}
              </span>
            </>
          )}
          <button className="action-btn" onClick={handleResetDb} title="Reseed deterministic data">
            🔄 Reset DB
          </button>
          <button className="action-btn" onClick={handleNewSession}>
            + New Session
          </button>
        </div>
      </header>

      {/* Main View Area */}
      {activeTab === "chat" ? (
        <Chat
          sessionId={sessionId}
          onNewSession={handleNewSession}
          onResetDb={handleResetDb}
        />
      ) : (
        <TraceViewer currentSessionId={sessionId} />
      )}
    </div>
  );
}
