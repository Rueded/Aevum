import { useCallback, useEffect, useState } from "react";
import "./App.css";
import { api } from "./api";
import { ChatView } from "./components/ChatView";
import { PresenceHeader } from "./components/PresenceHeader";
import { Sidebar } from "./components/Sidebar";
import {
  CharacterDebugResponse,
  CharacterStateResponse,
  ConversationDetail,
  HealthData,
  LifeResponse,
  MemoryItem,
  MessageItem,
  RelationshipResponse,
} from "./types";

const LOCAL_STORAGE_CONV_KEY = "aevum_active_conversation_id";

export function App() {
  // Backend & companion state
  const [health, setHealth] = useState<HealthData | null>(null);
  const [characterState, setCharacterState] = useState<CharacterStateResponse | null>(null);
  const [relationship, setRelationship] = useState<RelationshipResponse | null>(null);
  const [life, setLife] = useState<LifeResponse | null>(null);
  const [memories, setMemories] = useState<MemoryItem[]>([]);
  const [debugData, setDebugData] = useState<CharacterDebugResponse | null>(null);

  // Active chat session state
  const [activeConversationId, setActiveConversationId] = useState<string | null>(() => {
    return localStorage.getItem(LOCAL_STORAGE_CONV_KEY);
  });
  const [conversation, setConversation] = useState<ConversationDetail | null>(null);
  const [inputMessage, setInputMessage] = useState<string>("");
  const [lastFailedMessage, setLastFailedMessage] = useState<string | null>(null);
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [chatError, setChatError] = useState<string | null>(null);

  // Layout & panel state
  const [isSidebarOpen, setIsSidebarOpen] = useState<boolean>(false);
  const [activeTab, setActiveTab] = useState<"about" | "relationship" | "memories" | "debug">("about");

  // Load backend health
  const checkHealth = useCallback(async () => {
    try {
      const data = await api.getHealth();
      setHealth(data);
    } catch {
      setHealth(null);
    }
  }, []);

  // Refresh character domain state (read-only projection)
  const refreshCompanionState = useCallback(async () => {
    try {
      const [charData, relData, lifeData, memData] = await Promise.all([
        api.getCharacterState().catch(() => null),
        api.getRelationship().catch(() => null),
        api.getLife().catch(() => null),
        api.getMemories().catch(() => []),
      ]);

      if (charData) setCharacterState(charData);
      if (relData) setRelationship(relData);
      if (lifeData) setLife(lifeData);
      if (memData) setMemories(memData);
    } catch (err) {
      console.warn("Failed to refresh companion state:", err);
    }
  }, []);

  // Refresh debug data when tab is active
  const refreshDebugData = useCallback(async () => {
    try {
      const data = await api.getDebug();
      setDebugData(data);
    } catch (err) {
      console.warn("Failed to refresh debug data:", err);
    }
  }, []);

  // Fetch conversation messages
  const loadConversation = useCallback(async (convId: string) => {
    try {
      const data = await api.getConversation(convId);
      setConversation(data);
      setChatError(null);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Error loading conversation";
      if (msg.includes("404") || msg.includes("not found")) {
        // Conversation was deleted or reset
        localStorage.removeItem(LOCAL_STORAGE_CONV_KEY);
        setActiveConversationId(null);
        setConversation(null);
      } else {
        setChatError(msg);
      }
    }
  }, []);

  // Initialize or create conversation on demand
  const handleCreateNewConversation = useCallback(async () => {
    setChatError(null);
    setLastFailedMessage(null);
    try {
      const created = await api.createConversation();
      localStorage.setItem(LOCAL_STORAGE_CONV_KEY, created.id);
      setActiveConversationId(created.id);
      setConversation({
        id: created.id,
        created_at: created.created_at,
        updated_at: created.updated_at,
        messages: [],
      });
      await refreshCompanionState();
    } catch (err: unknown) {
      setChatError(err instanceof Error ? err.message : "Failed to create conversation");
    }
  }, [refreshCompanionState]);

  // Initial load
  useEffect(() => {
    checkHealth();
    refreshCompanionState();

    if (activeConversationId) {
      loadConversation(activeConversationId);
    } else {
      // Auto-create initial conversation if none saved
      handleCreateNewConversation();
    }
  }, [checkHealth, refreshCompanionState, activeConversationId, loadConversation, handleCreateNewConversation]);

  // Refresh debug data when debug tab is viewed
  useEffect(() => {
    if (isSidebarOpen && activeTab === "debug") {
      refreshDebugData();
    }
  }, [isSidebarOpen, activeTab, refreshDebugData]);

  // Send message with retry support
  const handleSendMessage = async (textToSend?: string) => {
    const content = (textToSend !== undefined ? textToSend : inputMessage).trim();
    if (!content || isGenerating) return;

    let convId = activeConversationId;
    if (!convId) {
      try {
        const created = await api.createConversation();
        convId = created.id;
        localStorage.setItem(LOCAL_STORAGE_CONV_KEY, convId);
        setActiveConversationId(convId);
      } catch (err: unknown) {
        setChatError(err instanceof Error ? err.message : "Failed to initialize conversation session");
        return;
      }
    }

    if (textToSend === undefined) {
      setInputMessage("");
    }
    setLastFailedMessage(null);
    setChatError(null);
    setIsGenerating(true);

    // Optimistically render user message immediately
    const tempUserMsg: MessageItem = {
      id: `temp-${Date.now()}`,
      conversation_id: convId,
      role: "user",
      content: content,
      created_at: new Date().toISOString(),
    };

    setConversation((prev) => ({
      id: convId!,
      created_at: prev?.created_at || new Date().toISOString(),
      updated_at: new Date().toISOString(),
      messages: [...(prev?.messages || []), tempUserMsg],
    }));

    try {
      const res = await api.sendMessage(convId, content);

      // Successfully generated and persisted
      if (res.assistant_response) {
        setConversation((prev) => {
          const filtered = (prev?.messages || []).filter((m) => m.id !== tempUserMsg.id);
          return {
            id: convId!,
            created_at: prev?.created_at || new Date().toISOString(),
            updated_at: new Date().toISOString(),
            messages: [...filtered, res.message, res.assistant_response!],
          };
        });
      } else {
        await loadConversation(convId);
      }

      setLastFailedMessage(null);

      // Update companion domain state in background (relationship, life, memories)
      refreshCompanionState();

      // P3: Refresh memories shortly after turn to sync post-turn background distillation
      setTimeout(() => {
        api.getMemories().then(setMemories).catch(() => {});
      }, 1500);

      if (isSidebarOpen && activeTab === "debug") {
        refreshDebugData();
      }
    } catch (err: unknown) {
      const errMsg = err instanceof Error ? err.message : "Failed to get response from Aevum";
      setChatError(`Response issue: ${errMsg}`);
      setLastFailedMessage(content);
      // Reload actual persisted messages from backend (user message is persisted even on 502)
      if (convId) {
        loadConversation(convId);
      }
    } finally {
      setIsGenerating(false);
    }
  };

  // Delete memory
  const handleDeleteMemory = async (memoryId: string) => {
    await api.deleteMemory(memoryId);
    setMemories((prev) => prev.filter((m) => m.id !== memoryId));
    if (isSidebarOpen && activeTab === "debug") {
      refreshDebugData();
    }
  };

  return (
    <div className="companion-app-root">
      <PresenceHeader
        health={health}
        characterState={characterState}
        isGenerating={isGenerating}
        onNewConversation={handleCreateNewConversation}
        isSidebarOpen={isSidebarOpen}
        onToggleSidebar={() => setIsSidebarOpen((prev) => !prev)}
        activeTab={activeTab}
        onSelectTab={(tab) => setActiveTab(tab)}
      />

      <div className="companion-main-body">
        <main className="chat-main-column">
          <ChatView
            messages={conversation?.messages || []}
            isGenerating={isGenerating}
            input={inputMessage}
            onInputChange={setInputMessage}
            onSendMessage={() => handleSendMessage()}
            error={chatError}
            onRetry={lastFailedMessage ? () => handleSendMessage(lastFailedMessage) : undefined}
            characterName={characterState?.name || "Aevum"}
          />
        </main>

        <Sidebar
          isOpen={isSidebarOpen}
          onClose={() => setIsSidebarOpen(false)}
          activeTab={activeTab}
          onSelectTab={setActiveTab}
          characterState={characterState}
          relationship={relationship}
          life={life}
          memories={memories}
          onDeleteMemory={handleDeleteMemory}
          debugData={debugData}
          activeConversationId={activeConversationId}
        />
      </div>
    </div>
  );
}

export default App;
