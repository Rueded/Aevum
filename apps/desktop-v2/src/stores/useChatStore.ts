import { create } from "zustand";

interface ChatStoreState {
  inputMessage: string;
  isGenerating: boolean;
  chatError: string | null;
  lastFailedMessage: string | null;
  messageQueue: string[];
  playingMessageId: string | null;
  highlightedMessageId: string | null;

  setInputMessage: (msg: string) => void;
  setIsGenerating: (generating: boolean) => void;
  setChatError: (err: string | null) => void;
  setLastFailedMessage: (msg: string | null) => void;
  enqueueMessage: (text: string) => void;
  drainMessageQueue: () => string | null;
  setPlayingMessageId: (id: string | null) => void;
  setHighlightedMessageId: (id: string | null) => void;
}

export const useChatStore = create<ChatStoreState>((set, get) => ({
  inputMessage: "",
  isGenerating: false,
  chatError: null,
  lastFailedMessage: null,
  messageQueue: [],
  playingMessageId: null,
  highlightedMessageId: null,

  setInputMessage: (inputMessage: string) => set({ inputMessage }),
  setIsGenerating: (isGenerating: boolean) => set({ isGenerating }),
  setChatError: (chatError: string | null) => set({ chatError }),
  setLastFailedMessage: (lastFailedMessage: string | null) => set({ lastFailedMessage }),

  enqueueMessage: (text: string) => {
    set((state) => ({ messageQueue: [...state.messageQueue, text] }));
  },

  drainMessageQueue: () => {
    const queue = get().messageQueue;
    if (queue.length === 0) return null;
    const combined = queue.join("\n");
    set({ messageQueue: [] });
    return combined;
  },

  setPlayingMessageId: (playingMessageId: string | null) => set({ playingMessageId }),
  setHighlightedMessageId: (highlightedMessageId: string | null) => set({ highlightedMessageId }),
}));
