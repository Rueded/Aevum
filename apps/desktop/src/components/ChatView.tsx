import React, { useEffect, useRef } from "react";
import { MessageItem } from "../types";

interface ChatViewProps {
  messages: MessageItem[];
  isGenerating: boolean;
  input: string;
  onInputChange: (val: string) => void;
  onSendMessage: () => void;
  error: string | null;
  onRetry?: () => void;
  characterName: string;
  highlightedMessageId?: string | null;
}

export const ChatView: React.FC<ChatViewProps> = ({
  messages,
  isGenerating,
  input,
  onInputChange,
  onSendMessage,
  error,
  onRetry,
  characterName,
  highlightedMessageId,
}) => {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll to bottom on new messages or generation change (unless highlighting a specific message)
  useEffect(() => {
    if (!highlightedMessageId && messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, isGenerating, highlightedMessageId]);

  // Scroll to highlighted message when requested via deep link
  useEffect(() => {
    if (highlightedMessageId) {
      const el = document.getElementById(`msg-${highlightedMessageId}`);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    }
  }, [highlightedMessageId]);

  // Adjust textarea height dynamically
  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    onInputChange(e.target.value);
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 160)}px`;
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (input.trim() && !isGenerating) {
        onSendMessage();
        if (textareaRef.current) {
          textareaRef.current.style.height = "auto";
        }
      }
    }
  };

  const formatTime = (isoString: string) => {
    try {
      const date = new Date(isoString);
      return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    } catch {
      return "";
    }
  };

  return (
    <div className="chat-view">
      <div className="messages-container" ref={scrollContainerRef}>
        {messages.length === 0 ? (
          <div className="chat-empty-state">
            <div className="empty-avatar">A</div>
            <h3>Conversation with {characterName}</h3>
            <p className="empty-subtext">
              Aevum is a self-grounded digital companion living her own routine, memories, and thoughts.
              Say hello or ask her what she is doing.
            </p>
            <div className="starter-chips">
              <button
                className="chip-btn"
                onClick={() => onInputChange("Hi Aevum, what have you been up to today?")}
              >
                "What have you been up to today?"
              </button>
              <button
                className="chip-btn"
                onClick={() => onInputChange("How are you feeling right now?")}
              >
                "How are you feeling right now?"
              </button>
              <button
                className="chip-btn"
                onClick={() => onInputChange("What kind of books or music do you enjoy?")}
              >
                "What kind of books or music do you enjoy?"
              </button>
            </div>
          </div>
        ) : (
          messages.map((msg) => {
            const isUser = msg.role === "user";
            return (
              <div
                key={msg.id}
                id={`msg-${msg.id}`}
                className={`message-row ${isUser ? "user-row" : "companion-row"} ${
                  highlightedMessageId === msg.id ? "highlighted-message" : ""
                }`}
              >
                {!isUser && <div className="bubble-avatar">A</div>}
                <div className={`message-bubble ${isUser ? "user-bubble" : "companion-bubble"}`}>
                  <div className="message-header-small">
                    <span className="sender-name">{isUser ? "You" : characterName}</span>
                    <span className="timestamp">{formatTime(msg.created_at)}</span>
                  </div>
                  <div className="bubble-text">
                    {msg.content.split("\n").map((line, idx) => (
                      <React.Fragment key={idx}>
                        {line}
                        {idx < msg.content.split("\n").length - 1 && <br />}
                      </React.Fragment>
                    ))}
                  </div>
                </div>
              </div>
            );
          })
        )}

        {isGenerating && (
          <div className="message-row companion-row">
            <div className="bubble-avatar">A</div>
            <div className="message-bubble companion-bubble typing-bubble">
              <div className="message-header-small">
                <span className="sender-name">{characterName}</span>
              </div>
              <div className="typing-indicator">
                <span className="dot" />
                <span className="dot" />
                <span className="dot" />
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {error && (
        <div className="chat-error-banner">
          <span className="error-text">{error}</span>
          {onRetry && (
            <button className="error-retry-btn" onClick={onRetry}>
              Retry
            </button>
          )}
        </div>
      )}

      <div className="chat-input-area">
        <div className="input-wrapper">
          <textarea
            ref={textareaRef}
            className="chat-textarea"
            rows={1}
            placeholder={`Message ${characterName}... (Enter to send, Shift+Enter for newline)`}
            value={input}
            onChange={handleInput}
            onKeyDown={handleKeyDown}
            disabled={isGenerating}
          />
          <button
            className="send-button"
            onClick={() => {
              if (input.trim() && !isGenerating) {
                onSendMessage();
                if (textareaRef.current) {
                  textareaRef.current.style.height = "auto";
                }
              }
            }}
            disabled={!input.trim() || isGenerating}
            title="Send message"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" className="send-icon">
              <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
};
