import { create } from "zustand";
import { api } from "../api";
import type { ConversationListItem, ConversationDetail, MessageItem } from "../types";

const ACTIVE_CONVERSATION_KEY = "aevum_active_conversation_id";

interface ConversationStoreState {
  conversations: ConversationListItem[];
  activeConversationId: string | null;
  currentConversation: ConversationDetail | null;
  isLoadingList: boolean;
  isLoadingDetail: boolean;

  fetchConversations: () => Promise<void>;
  selectConversation: (id: string) => Promise<void>;
  createConversation: () => Promise<string>;
  deleteConversation: (id: string) => Promise<void>;
  loadActiveOrCreate: () => Promise<void>;
  addOptimisticMessage: (msg: MessageItem) => void;
  updateMessage: (id: string, updates: Partial<MessageItem>) => void;
}

export const useConversationStore = create<ConversationStoreState>((set, get) => ({
  conversations: [],
  activeConversationId: localStorage.getItem(ACTIVE_CONVERSATION_KEY),
  currentConversation: null,
  isLoadingList: false,
  isLoadingDetail: false,

  fetchConversations: async () => {
    set({ isLoadingList: true });
    try {
      const list = await api.getConversations(50);
      set({ conversations: list });
    } catch (e) {
      console.error("Failed to fetch conversations", e);
    } finally {
      set({ isLoadingList: false });
    }
  },

  selectConversation: async (id: string) => {
    set({ activeConversationId: id, isLoadingDetail: true });
    localStorage.setItem(ACTIVE_CONVERSATION_KEY, id);
    try {
      const detail = await api.getConversation(id);
      set({ currentConversation: detail });
    } catch (e) {
      console.error(`Failed to load conversation ${id}`, e);
    } finally {
      set({ isLoadingDetail: false });
    }
  },

  createConversation: async () => {
    const res = await api.createConversation();
    localStorage.setItem(ACTIVE_CONVERSATION_KEY, res.id);
    set({
      activeConversationId: res.id,
      currentConversation: {
        id: res.id,
        created_at: res.created_at,
        updated_at: res.updated_at,
        messages: [],
      },
    });
    get().fetchConversations();
    return res.id;
  },

  deleteConversation: async (id: string) => {
    await api.deleteConversation(id);
    const remaining = get().conversations.filter((c) => c.id !== id);
    set({ conversations: remaining });

    if (get().activeConversationId === id) {
      if (remaining.length > 0) {
        await get().selectConversation(remaining[0].id);
      } else {
        await get().createConversation();
      }
    }
  },

  loadActiveOrCreate: async () => {
    try {
      await get().fetchConversations();
      const list = get().conversations;
      if (list.length > 0) {
        await get().selectConversation(list[0].id);
        return;
      }
    } catch (e) {
      console.warn("Failed to load existing conversation, falling back to new conversation:", e);
    }

    await get().createConversation();
  },

  addOptimisticMessage: (msg: MessageItem) => {
    set((state) => {
      if (!state.currentConversation) return state;
      return {
        currentConversation: {
          ...state.currentConversation,
          messages: [...state.currentConversation.messages, msg],
        },
      };
    });
  },

  updateMessage: (id: string, updates: Partial<MessageItem>) => {
    set((state) => {
      if (!state.currentConversation) return state;
      return {
        currentConversation: {
          ...state.currentConversation,
          messages: state.currentConversation.messages.map((m) =>
            m.id === id ? { ...m, ...updates } : m
          ),
        },
      };
    });
  },
}));
