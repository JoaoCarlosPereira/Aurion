// StatusIndicator.tsx — Indicador visual (ponto colorido + rotulo) de um estado.
// Componente compartilhado de infraestrutura, usado por SystemStatus e telas.

import { SYSTEM_STATE_META } from "@/hooks/useSystemState";
import type { SystemState } from "@/types";

export interface StatusIndicatorProps {
  state: SystemState;
  /** Exibe o rotulo textual ao lado do ponto (padrao: true). */
  showLabel?: boolean;
}

/** Mostra um ponto neon com a cor do estado e o rotulo correspondente. */
export function StatusIndicator({
  state,
  showLabel = true,
}: StatusIndicatorProps) {
  const meta = SYSTEM_STATE_META[state];
  return (
    <span className="inline-flex items-center gap-2">
      <span
        className="inline-block h-2.5 w-2.5 rounded-full"
        style={{ backgroundColor: meta.color, boxShadow: `0 0 8px ${meta.color}` }}
        aria-hidden="true"
      />
      {showLabel && (
        <span className="text-sm text-slate-200">{meta.label}</span>
      )}
    </span>
  );
}

export default StatusIndicator;
