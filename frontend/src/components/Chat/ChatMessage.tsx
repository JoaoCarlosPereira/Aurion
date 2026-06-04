// ChatMessage.tsx — Renderizacao de uma unica mensagem do painel de chat.
// Diferencia visualmente usuario, Aurion (assistant) e mensagens de sistema/erro,
// exibe horario, estado de "processando" e o player de audio TTS quando houver.

import { AudioPlayer } from "@/components/AudioPlayer/AudioPlayer";
import type { ChatMessage as ChatMessageModel } from "@/types";

export interface ChatMessageProps {
  /** Mensagem a ser renderizada. */
  message: ChatMessageModel;
}

/** Formata um timestamp ISO 8601 em HH:MM (pt-BR), com fallback seguro. */
function formatTime(timestamp: string): string {
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  return date.toLocaleTimeString("pt-BR", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** Rotulo do autor exibido acima do balao da mensagem. */
function roleLabel(message: ChatMessageModel): string {
  if (message.role === "user") {
    return "Voce";
  }
  if (message.role === "assistant") {
    return "Aurion";
  }
  return "Sistema";
}

/**
 * Exibe uma mensagem individual no chat.
 *
 * - Mensagens do usuario alinham a direita (tema amarelo).
 * - Mensagens da Aurion alinham a esquerda (tema ciano).
 * - Mensagens de sistema/erro ficam centralizadas com destaque.
 */
export function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === "user";
  const isSystem = message.role === "system";
  const isError = message.error === true;

  // Mensagens de sistema/erro ocupam a largura toda, centralizadas.
  if (isSystem || isError) {
    return (
      <div
        className="my-1 flex justify-center"
        data-testid="chat-message"
        data-role={message.role}
        data-error={isError ? "true" : "false"}
      >
        <div
          role={isError ? "alert" : "status"}
          className={[
            "max-w-[80%] rounded-xl px-4 py-2 text-center text-sm",
            isError
              ? "border border-[#ef4444]/50 bg-[#ef4444]/10 text-[#ef4444]"
              : "border border-cyan/20 bg-pacman-bg/50 text-slate-400",
          ].join(" ")}
        >
          {message.text}
        </div>
      </div>
    );
  }

  const time = formatTime(message.timestamp);

  return (
    <div
      className={["my-2 flex", isUser ? "justify-end" : "justify-start"].join(
        " ",
      )}
      data-testid="chat-message"
      data-role={message.role}
      data-pending={message.pending ? "true" : "false"}
    >
      <div className="flex max-w-[80%] flex-col gap-1">
        <span
          className={[
            "px-1 text-xs font-semibold",
            isUser ? "self-end text-pacman-yellow" : "self-start text-cyan",
          ].join(" ")}
        >
          {roleLabel(message)}
          {time && <span className="ml-2 text-slate-500">{time}</span>}
        </span>

        <div
          className={[
            "rounded-2xl px-4 py-2 text-sm leading-relaxed backdrop-blur",
            isUser
              ? "rounded-br-sm border border-pacman-yellow/40 bg-pacman-yellow/10 text-slate-100"
              : "rounded-bl-sm border border-cyan/30 bg-cyan/10 text-slate-100",
          ].join(" ")}
        >
          {message.pending ? (
            <span
              className="inline-flex items-center gap-2 text-slate-300"
              aria-live="polite"
            >
              <span className="h-2 w-2 animate-pulse rounded-full bg-cyan" />
              Pensando...
            </span>
          ) : (
            <span className="whitespace-pre-wrap break-words">
              {message.text}
            </span>
          )}
        </div>

        {/* Player de audio TTS associado a resposta da Aurion, quando houver. */}
        {message.audioUrl && (
          <div className="mt-1">
            <AudioPlayer src={message.audioUrl} />
          </div>
        )}
      </div>
    </div>
  );
}

export default ChatMessage;
