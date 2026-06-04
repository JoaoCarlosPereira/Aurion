// HistoryItem.tsx — Item individual do historico de interacoes.
// Renderiza timestamp, canal (local/web), input/output e status, com
// expand/collapse para exibir detalhes adicionais da interacao.

import { useState } from "react";
import type { Channel, Interaction, InteractionStatus } from "@/types";

/** Cor de borda/realce por status (paleta TechSpec 6.2). */
const STATUS_COLORS: Record<InteractionStatus, string> = {
  success: "#22c55e",
  error: "#ef4444",
  timeout: "#ffd166",
};

/** Rotulo legivel em PT-BR por status. */
const STATUS_LABELS: Record<InteractionStatus, string> = {
  success: "Sucesso",
  error: "Erro",
  timeout: "Tempo esgotado",
};

/** Rotulo e cor do badge de canal. */
const CHANNEL_LABELS: Record<Channel, string> = {
  local: "Local",
  web: "Web",
};

/** Formata um timestamp ISO 8601 para exibicao em pt-BR. */
function formatTimestamp(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    // Mantem o valor bruto caso nao seja uma data valida.
    return iso;
  }
  return date.toLocaleString("pt-BR");
}

/** Props do item de historico. */
export interface HistoryItemProps {
  interaction: Interaction;
}

/** Item individual da lista de historico, com expand/collapse de detalhes. */
export function HistoryItem({ interaction }: HistoryItemProps) {
  const [expanded, setExpanded] = useState(false);

  const statusColor = STATUS_COLORS[interaction.status];

  return (
    <li
      className="rounded-xl border border-cyan/20 bg-pacman-bg/40 backdrop-blur"
      style={{ borderLeft: `3px solid ${statusColor}` }}
      data-testid="history-item"
    >
      <button
        type="button"
        className="flex w-full flex-col gap-1 px-4 py-3 text-left"
        onClick={() => setExpanded((value) => !value)}
        aria-expanded={expanded}
      >
        <div className="flex flex-wrap items-center gap-2">
          {/* Badge de canal (local vs web). */}
          <span
            className="rounded-md px-2 py-0.5 text-xs font-semibold"
            style={{
              color: interaction.channel === "local" ? "#34d3ff" : "#ffd166",
              border: `1px solid ${
                interaction.channel === "local" ? "#34d3ff" : "#ffd166"
              }`,
            }}
            data-testid="history-channel"
          >
            {CHANNEL_LABELS[interaction.channel]}
          </span>

          {/* Badge de status. */}
          <span
            className="rounded-md px-2 py-0.5 text-xs font-semibold"
            style={{ color: statusColor, border: `1px solid ${statusColor}` }}
            data-testid="history-status"
          >
            {STATUS_LABELS[interaction.status]}
          </span>

          {/* Timestamp formatado. */}
          <time
            className="ml-auto text-xs text-slate-400"
            dateTime={interaction.timestamp}
            data-testid="history-timestamp"
          >
            {formatTimestamp(interaction.timestamp)}
          </time>
        </div>

        {/* Texto de entrada (comando do usuario). */}
        <p className="truncate text-sm font-medium text-slate-100">
          {interaction.input_text}
        </p>

        {/* Previa da resposta quando recolhido. */}
        {!expanded && interaction.output_text ? (
          <p className="truncate text-sm text-slate-400">
            {interaction.output_text}
          </p>
        ) : null}
      </button>

      {/* Detalhes expandidos. */}
      {expanded ? (
        <div
          className="flex flex-col gap-3 border-t border-cyan/10 px-4 py-3 text-sm"
          data-testid="history-details"
        >
          <div>
            <span className="text-xs font-semibold uppercase text-cyan">
              Entrada
            </span>
            <p className="whitespace-pre-wrap text-slate-200">
              {interaction.input_text}
            </p>
          </div>

          <div>
            <span className="text-xs font-semibold uppercase text-cyan">
              Resposta
            </span>
            <p className="whitespace-pre-wrap text-slate-200">
              {interaction.output_text ?? "—"}
            </p>
          </div>

          {interaction.error_message ? (
            <div>
              <span className="text-xs font-semibold uppercase text-red-400">
                Mensagem de erro
              </span>
              <p className="whitespace-pre-wrap text-red-300">
                {interaction.error_message}
              </p>
            </div>
          ) : null}

          {interaction.duration_ms != null ? (
            <p className="text-xs text-slate-400">
              Duracao: {interaction.duration_ms} ms
            </p>
          ) : null}

          {interaction.output_audio_url ? (
            <audio
              controls
              src={interaction.output_audio_url}
              className="w-full"
              data-testid="history-audio"
            />
          ) : null}
        </div>
      ) : null}
    </li>
  );
}

export default HistoryItem;
