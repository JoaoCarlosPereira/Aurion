// useSystemState.ts — Conecta /ws/status ao store global e expoe o estado atual.
// Deve ser montado uma vez no topo da aplicacao (ex: App) para manter o estado vivo.

import { useEffect } from "react";
import { useAurionStore } from "@/store/aurionStore";
import { useWebSocket } from "@/hooks/useWebSocket";
import { wsPaths } from "@/services/websocket";
import type { StatusMessage, SystemState } from "@/types";

/** Metadados visuais de cada estado do sistema (TechSpec 6.2). */
export interface SystemStateMeta {
  label: string;
  color: string;
}

/** Mapa de estados para rotulo PT-BR e cor (paleta da TechSpec 6.2). */
export const SYSTEM_STATE_META: Record<SystemState, SystemStateMeta> = {
  idle: { label: "Inativo", color: "#6b7280" },
  listening: { label: "Escutando", color: "#3b82f6" },
  detecting: { label: "Wake word detectada", color: "#34d3ff" },
  stt: { label: "Ouvindo fala", color: "#8b5cf6" },
  processing: { label: "Processando", color: "#ffd166" },
  tts: { label: "Falando", color: "#22c55e" },
  error: { label: "Erro", color: "#ef4444" },
};

/** Valor de retorno do hook useSystemState. */
export interface UseSystemStateResult {
  systemState: SystemState;
  statusMessage: string | null;
  meta: SystemStateMeta;
  connected: boolean;
}

/**
 * Assina o canal /ws/status, sincroniza o estado no store global e o retorna.
 */
export function useSystemState(): UseSystemStateResult {
  const systemState = useAurionStore((s) => s.systemState);
  const statusMessage = useAurionStore((s) => s.statusMessage);
  const setSystemState = useAurionStore((s) => s.setSystemState);
  const setWsStatus = useAurionStore((s) => s.setWsStatus);

  const { status } = useWebSocket<StatusMessage>({
    path: wsPaths.status(),
    onMessage: (data) => {
      setSystemState(data.state, data.message ?? null);
    },
  });

  useEffect(() => {
    setWsStatus(status);
  }, [status, setWsStatus]);

  return {
    systemState,
    statusMessage,
    meta: SYSTEM_STATE_META[systemState],
    connected: status === "open",
  };
}
