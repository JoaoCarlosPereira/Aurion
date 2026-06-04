// aurionStore.ts — Estado global da SPA via Zustand.
// Centraliza estado do sistema, mensagens de chat, configuracao e conexao WS.
// As tasks 13-17 consomem este store sem precisar edita-lo.

import { create } from "zustand";
import type {
  AppConfig,
  ChatMessage,
  SystemState,
} from "@/types";
import type { WSStatus } from "@/services/websocket";

/** Forma do estado global do Aurion. */
export interface AurionStore {
  // Estado do pipeline de voz (recebido via /ws/status).
  systemState: SystemState;
  statusMessage: string | null;
  setSystemState: (state: SystemState, message?: string | null) => void;

  // Conexao WebSocket de status.
  wsStatus: WSStatus;
  setWsStatus: (status: WSStatus) => void;

  // Mensagens do painel de chat (estado de UI).
  messages: ChatMessage[];
  addMessage: (message: ChatMessage) => void;
  updateMessage: (id: string, patch: Partial<ChatMessage>) => void;
  removeMessage: (id: string) => void;
  clearMessages: () => void;

  // Configuracao da aplicacao.
  config: AppConfig | null;
  setConfig: (config: AppConfig) => void;
}

/** Store global compartilhado por toda a aplicacao. */
export const useAurionStore = create<AurionStore>((set) => ({
  systemState: "idle",
  statusMessage: null,
  setSystemState: (state, message = null) =>
    set({ systemState: state, statusMessage: message }),

  wsStatus: "closed",
  setWsStatus: (status) => set({ wsStatus: status }),

  messages: [],
  addMessage: (message) =>
    set((prev) => ({ messages: [...prev.messages, message] })),
  updateMessage: (id, patch) =>
    set((prev) => ({
      messages: prev.messages.map((m) =>
        m.id === id ? { ...m, ...patch } : m,
      ),
    })),
  removeMessage: (id) =>
    set((prev) => ({ messages: prev.messages.filter((m) => m.id !== id) })),
  clearMessages: () => set({ messages: [] }),

  config: null,
  setConfig: (config) => set({ config }),
}));
