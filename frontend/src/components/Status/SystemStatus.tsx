// SystemStatus.tsx — Barra de status do sistema, assina /ws/status via hook.
// Placeholder de infraestrutura: exibe estado atual e conexao do WebSocket.

import { useSystemState } from "@/hooks/useSystemState";
import { StatusIndicator } from "@/components/Status/StatusIndicator";

/** Exibe o estado atual do pipeline de voz e o status da conexao. */
export function SystemStatus() {
  const { systemState, statusMessage, connected } = useSystemState();
  return (
    <div className="flex items-center gap-3 rounded-xl border border-cyan/30 bg-pacman-bg/60 px-4 py-2 backdrop-blur">
      <StatusIndicator state={systemState} />
      {statusMessage && (
        <span className="text-xs text-slate-400">{statusMessage}</span>
      )}
      <span
        className="ml-auto text-xs"
        style={{ color: connected ? "#22c55e" : "#ef4444" }}
      >
        {connected ? "WS conectado" : "WS desconectado"}
      </span>
    </div>
  );
}

export default SystemStatus;
