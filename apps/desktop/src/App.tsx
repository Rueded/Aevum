import { useEffect, useState, useCallback, FormEvent } from "react";
import "./App.css";

interface HealthData {
  status: string;
  app: string;
  version: string;
  database: string;
}

interface MessageItem {
  id: string;
  conversation_id: string;
  role: string;
  content: string;
  created_at: string;
}

interface ConversationDetail {
  id: string;
  created_at: string;
  updated_at: string;
  messages: MessageItem[];
}

const BACKEND_BASE_URL = "http://127.0.0.1:8000";
const LOCAL_STORAGE_CONV_KEY = "aevum_active_conversation_id";

export function App() {
  // Backend health state
  const [health, setHealth] = useState<HealthData | null>(null);
  const [backendError, setBackendError] = useState<string | null>(null);

  // Conversation state
  const [activeConversationId, setActiveConversationId] = useState<string | null>(() => {
    return localStorage.getItem(LOCAL_STORAGE_CONV_KEY);
  });
  const [conversation, setConversation] = useState<ConversationDetail | null>(null);
  const [loadingConversation, setLoadingConversation] = useState<boolean>(false);
  const [conversationError, setConversationError] = useState<string | null>(null);

  // Message input & generation state
  const [messageInput, setMessageInput] = useState<string>("");
  const [sendingMessage, setSendingMessage] = useState<boolean>(false);
  const [actionFeedback, setActionFeedback] = useState<string | null>(null);

  // Check health
  const checkHealth = useCallback(async () => {
    try {
      const res = await fetch(`${BACKEND_BASE_URL}/health`);
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      const data: HealthData = await res.json();
      setHealth(data);
      setBackendError(null);
    } catch (err: unknown) {
      setHealth(null);
      setBackendError(err instanceof Error ? err.message : "Failed to connect");
    }
  }, []);

  // Fetch active conversation from database
  const fetchConversation = useCallback(async (convId: string) => {
    setLoadingConversation(true);
    setConversationError(null);
    try {
      const res = await fetch(`${BACKEND_BASE_URL}/conversations/${convId}`);
      if (res.status === 404) {
        localStorage.removeItem(LOCAL_STORAGE_CONV_KEY);
        setActiveConversationId(null);
        setConversation(null);
        setConversationError(`Conversation ${convId} not found in database (may have been reset).`);
        return;
      }
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      const data: ConversationDetail = await res.json();
      setConversation(data);
    } catch (err: unknown) {
      setConversationError(err instanceof Error ? err.message : "Error fetching conversation");
    } finally {
      setLoadingConversation(false);
    }
  }, []);

  // Create new conversation in backend
  const handleCreateConversation = async () => {
    setLoadingConversation(true);
    setConversationError(null);
    setActionFeedback(null);
    try {
      const res = await fetch(`${BACKEND_BASE_URL}/conversations`, {
        method: "POST",
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      const created: { id: string } = await res.json();
      localStorage.setItem(LOCAL_STORAGE_CONV_KEY, created.id);
      setActiveConversationId(created.id);
      await fetchConversation(created.id);
      setActionFeedback(`Created new persistent conversation: ${created.id}`);
    } catch (err: unknown) {
      setConversationError(err instanceof Error ? err.message : "Failed to create conversation");
      setLoadingConversation(false);
    }
  };

  // Send message to backend and receive assistant generation
  const handleSendMessage = async (e: FormEvent) => {
    e.preventDefault();
    const trimmed = messageInput.trim();
    if (!trimmed || !activeConversationId) return;

    setSendingMessage(true);
    setConversationError(null);
    setActionFeedback(null);

    try {
      const res = await fetch(`${BACKEND_BASE_URL}/conversations/${activeConversationId}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ role: "user", content: trimmed }),
      });

      if (!res.ok) {
        const errorBody = await res.json().catch(() => null);
        const detail = errorBody?.detail || `HTTP ${res.status}: ${res.statusText}`;

        // In case of 502/503, user message was still committed in DB; refetch to display it
        await fetchConversation(activeConversationId);
        throw new Error(`LLM generation error (${res.status}): ${detail}`);
      }

      setMessageInput("");
      // Refetch conversation to display user message and newly persisted assistant reply
      await fetchConversation(activeConversationId);
      setActionFeedback("Assistant response generated via Gemini and persisted to SQLite.");
    } catch (err: unknown) {
      setConversationError(err instanceof Error ? err.message : "Failed to process message");
    } finally {
      setSendingMessage(false);
    }
  };

  // Clear local ID
  const handleClearLocalId = () => {
    localStorage.removeItem(LOCAL_STORAGE_CONV_KEY);
    setActiveConversationId(null);
    setConversation(null);
    setActionFeedback("Cleared active conversation ID from localStorage.");
  };

  // Initial load
  useEffect(() => {
    checkHealth();
  }, [checkHealth]);

  useEffect(() => {
    if (activeConversationId) {
      fetchConversation(activeConversationId);
    }
  }, [activeConversationId, fetchConversation]);

  return (
    <div className="container">
      <header className="header">
        <h1 className="title">Aevum</h1>
        <p className="tagline">A Persistent Digital Life</p>
        <div className="phase-badge">Phase 6.3: First Playable Conversation</div>
      </header>

      {/* Backend Health Banner */}
      <div className="health-bar">
        <div className="health-bar-left">
          <span
            className={`dot ${
              health?.status === "ok" ? "green" : backendError ? "red" : "yellow"
            }`}
          ></span>
          <span className="health-label">
            Core Backend:{" "}
            <strong>
              {health?.status === "ok" ? "Online (SQLite Connected)" : backendError ? "Offline" : "Checking..."}
            </strong>
          </span>
        </div>
        <button className="btn-secondary" onClick={checkHealth}>
          Check Health
        </button>
      </div>

      {backendError && (
        <div className="error-box">
          <strong>Backend Connection Error:</strong> {backendError}
        </div>
      )}

      {/* Conversation Session Controls */}
      <section className="card">
        <div className="card-header">
          <h2 className="card-title">Conversation Session</h2>
          <div className="button-group">
            <button
              className="btn-primary"
              onClick={handleCreateConversation}
              disabled={loadingConversation || sendingMessage}
            >
              + New Conversation
            </button>
            {activeConversationId && (
              <>
                <button
                  className="btn-secondary"
                  onClick={() => fetchConversation(activeConversationId)}
                  disabled={loadingConversation || sendingMessage}
                >
                  Reload from DB
                </button>
                <button
                  className="btn-outline"
                  onClick={handleClearLocalId}
                  disabled={sendingMessage}
                >
                  Clear Local ID
                </button>
              </>
            )}
          </div>
        </div>

        <div className="session-meta">
          <div className="meta-item">
            <span className="meta-label">Active Conversation ID:</span>
            <code className="meta-value">
              {activeConversationId || "None (Create a conversation to begin)"}
            </code>
          </div>
          {conversation && (
            <div className="meta-item">
              <span className="meta-label">Created At:</span>
              <span className="meta-value">
                {new Date(conversation.created_at).toLocaleString()}
              </span>
            </div>
          )}
        </div>

        {conversationError && (
          <div className="error-box">
            <strong>Notice:</strong> {conversationError}
          </div>
        )}

        {actionFeedback && <div className="feedback-box">{actionFeedback}</div>}

        {/* Persisted Messages Display */}
        <div className="messages-section">
          <h3 className="section-title">
            Persisted Messages ({conversation?.messages.length ?? 0})
          </h3>

          {!activeConversationId ? (
            <div className="empty-state">
              No active conversation selected. Click <strong>+ New Conversation</strong> to start.
            </div>
          ) : loadingConversation ? (
            <div className="loading-state">Loading messages from SQLite database...</div>
          ) : conversation?.messages && conversation.messages.length > 0 ? (
            <div className="message-list">
              {conversation.messages.map((msg) => (
                <div key={msg.id} className={`message-item ${msg.role}`}>
                  <div className="message-header">
                    <span className={`role-badge ${msg.role}`}>
                      {msg.role === "assistant" ? "AEVUM (GEMINI)" : msg.role.toUpperCase()}
                    </span>
                    <span className="message-time">
                      {new Date(msg.created_at).toLocaleTimeString()}
                    </span>
                  </div>
                  <div className="message-content">{msg.content}</div>
                </div>
              ))}
              {sendingMessage && (
                <div className="message-item assistant" style={{ opacity: 0.7 }}>
                  <div className="message-header">
                    <span className="role-badge assistant">AEVUM (GENERATING...)</span>
                  </div>
                  <div className="message-content" style={{ fontStyle: "italic", color: "#8b949e" }}>
                    Generating response from Gemini...
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="empty-state">
              No messages in this conversation yet. Send a message below to begin.
            </div>
          )}
        </div>

        {/* Message Sender Form */}
        {activeConversationId && (
          <form className="message-form" onSubmit={handleSendMessage}>
            <input
              type="text"
              className="message-input"
              placeholder={
                sendingMessage
                  ? "Waiting for Gemini response..."
                  : "Type a message to converse with Gemini..."
              }
              value={messageInput}
              onChange={(e) => setMessageInput(e.target.value)}
              disabled={sendingMessage || loadingConversation}
            />
            <button
              type="submit"
              className="btn-primary"
              disabled={sendingMessage || loadingConversation || !messageInput.trim()}
            >
              {sendingMessage ? "Generating..." : "Send Message"}
            </button>
          </form>
        )}
      </section>

      {/* Architectural Reality Note */}
      <aside className="note-box">
        <strong>Architecture Principle:</strong> The application owns reality; the LLM generates language. This desktop client renders conversation history persisted in SQLite. The Gemini provider translates conversation context into natural language without owning character state, memory, or personality.
      </aside>
    </div>
  );
}

export default App;
