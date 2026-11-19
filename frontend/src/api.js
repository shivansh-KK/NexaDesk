const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export async function sendMessage(sessionId, message) {
  const res = await fetch(`${BASE_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, message }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Failed to send message");
  }
  return res.json();
}

export async function confirmAction(sessionId, actionId, confirm) {
  const res = await fetch(`${BASE_URL}/chat/confirm`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, action_id: actionId, confirm }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Failed to confirm action");
  }
  return res.json();
}

export async function getSessionHistory(sessionId) {
  const res = await fetch(`${BASE_URL}/sessions/${sessionId}`);
  if (!res.ok) throw new Error("Failed to load session history");
  return res.json();
}

export async function getTraces(sessionId = null, limit = 100) {
  const url = sessionId
    ? `${BASE_URL}/traces?session_id=${encodeURIComponent(sessionId)}&limit=${limit}`
    : `${BASE_URL}/traces?limit=${limit}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error("Failed to load traces");
  return res.json();
}

export async function getHealth() {
  const res = await fetch(`${BASE_URL}/health`);
  if (!res.ok) throw new Error("Backend offline");
  return res.json();
}

export async function resetDatabase() {
  const res = await fetch(`${BASE_URL}/admin/reset-db`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to reset database");
  return res.json();
}
