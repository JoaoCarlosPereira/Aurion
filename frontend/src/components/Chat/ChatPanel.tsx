// ChatPanel.tsx — Painel principal de chat do Aurion.
//
// Responsabilidades (task 13):
// - Renderizar a lista de mensagens (ChatMessage) com auto-scroll.
// - Enviar comandos por texto via POST /api/command (useAurionAPI) e exibir loading.
// - Receber a resposta correlacionada por id (GET /api/command/{id}, polling).
// - Refletir o estado do sistema via /ws/status (SystemStatus / useSystemState).
// - Receber audio TTS via /ws/audio/{session_id} e anexar a resposta da Aurion.
// - Tratar falhas mostrando "Hermes indisponivel" no chat.
// - Estado das mensagens centralizado no store Zustand (useAurionStore).

import { useCallback, useEffect, useMemo, useRef } from "react";
import { ChatMessage } from "@/components/Chat/ChatMessage";
import { ChatInput } from "@/components/Chat/ChatInput";
import { SystemStatus } from "@/components/Status/SystemStatus";
import { MicButton } from "@/components/MicButton/MicButton";
import { useAurionAPI } from "@/hooks/useAurionAPI";
import { useWebSocket } from "@/hooks/useWebSocket";
import { useAurionStore } from "@/store/aurionStore";
import { wsPaths } from "@/services/websocket";
import type {
  AudioChunkMessage,
  ChatMessage as ChatMessageModel,
  Interaction,
} from "@/types";

/** Intervalo entre tentativas de leitura do resultado do comando (ms). */
const POLL_INTERVAL_MS = 800;
/** Numero maximo de tentativas de polling antes de desistir (~24s). */
const MAX_POLL_ATTEMPTS = 30;

/** Gera um identificador local simples para mensagens e sessao. */
function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

/** Pausa assincrona utilitaria para o loop de polling. */
function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/** Decodifica base64 -> Uint8Array para montar o Blob de audio. */
function base64ToBytes(base64: string): Uint8Array {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}

/** Painel de conversa do Aurion. */
export function ChatPanel() {
  const api = useAurionAPI();

  // Estado de mensagens vindo do store global (Zustand).
  const messages = useAurionStore((s) => s.messages);
  const addMessage = useAurionStore((s) => s.addMessage);
  const updateMessage = useAurionStore((s) => s.updateMessage);

  // Identificador estavel da sessao web, usado no canal /ws/audio.
  const sessionId = useMemo(() => generateId(), []);

  // Referencia para auto-scroll e para o id da mensagem da Aurion "em voo".
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const pendingAssistantIdRef = useRef<string | null>(null);
  // Acumula chunks de audio TTS recebidos via WebSocket.
  const audioChunksRef = useRef<Uint8Array[]>([]);

  // Indica se ha um comando em processamento (desabilita o input).
  const isLoading = messages.some((m) => m.pending);

  // Auto-scroll para a ultima mensagem sempre que a lista muda.
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Canal de audio TTS: monta um Blob e anexa a resposta pendente da Aurion.
  useWebSocket<AudioChunkMessage>({
    path: wsPaths.audio(sessionId),
    onMessage: (data) => {
      if (data.type !== "audio_chunk" || !data.data) {
        return;
      }
      audioChunksRef.current.push(base64ToBytes(data.data));
      const targetId = pendingAssistantIdRef.current;
      if (!targetId) {
        return;
      }
      // Reconstroi a URL do audio acumulado a cada chunk (reproducao progressiva).
      const blob = new Blob(audioChunksRef.current as BlobPart[], {
        type: "audio/mpeg",
      });
      updateMessage(targetId, { audioUrl: URL.createObjectURL(blob) });
    },
  });

  /**
   * Faz polling do resultado de um comando ate obter resposta final ou falhar.
   * Atualiza a mensagem placeholder da Aurion com o texto/erro retornado.
   */
  const awaitCommandResult = useCallback(
    async (commandId: string, assistantId: string) => {
      for (let attempt = 0; attempt < MAX_POLL_ATTEMPTS; attempt += 1) {
        try {
          const result: Interaction = await api.getCommand(commandId);

          if (result.status === "success") {
            updateMessage(assistantId, {
              text: result.output_text ?? "",
              audioUrl: result.output_audio_url ?? undefined,
              pending: false,
            });
            return;
          }

          if (result.status === "error" || result.status === "timeout") {
            updateMessage(assistantId, {
              text:
                result.error_message ??
                "Ocorreu um erro ao processar o comando.",
              pending: false,
              error: true,
            });
            return;
          }
          // status "processing": aguarda e tenta novamente.
        } catch {
          // Erro de rede/Hermes: mensagem padrao da TechSpec (10.1).
          updateMessage(assistantId, {
            text: "Hermes indisponivel",
            pending: false,
            error: true,
          });
          return;
        }
        await delay(POLL_INTERVAL_MS);
      }

      // Esgotou as tentativas sem resposta final.
      updateMessage(assistantId, {
        text: "Tempo de resposta esgotado. Tente novamente.",
        pending: false,
        error: true,
      });
    },
    [api, updateMessage],
  );

  /** Envia o comando do usuario e prepara a mensagem da Aurion. */
  const handleSend = useCallback(
    async (text: string) => {
      const now = new Date().toISOString();

      const userMessage: ChatMessageModel = {
        id: generateId(),
        role: "user",
        text,
        timestamp: now,
      };
      addMessage(userMessage);

      const assistantId = generateId();
      const assistantMessage: ChatMessageModel = {
        id: assistantId,
        role: "assistant",
        text: "",
        timestamp: new Date().toISOString(),
        pending: true,
      };
      addMessage(assistantMessage);

      // Reinicia o buffer de audio e marca a resposta como alvo do canal /ws/audio.
      audioChunksRef.current = [];
      pendingAssistantIdRef.current = assistantId;

      try {
        const response = await api.sendCommand(text);
        await awaitCommandResult(response.id, assistantId);
      } catch {
        updateMessage(assistantId, {
          text: "Hermes indisponivel",
          pending: false,
          error: true,
        });
      } finally {
        pendingAssistantIdRef.current = null;
      }
    },
    [addMessage, api, awaitCommandResult, updateMessage],
  );

  return (
    <section className="flex h-full flex-col gap-4" aria-label="Chat">
      {/* Indicador de estado do sistema (cores da TechSpec 6.2) + status do WS. */}
      <SystemStatus />

      {/* Lista de mensagens com auto-scroll. */}
      <div
        className="flex-1 overflow-y-auto rounded-2xl border border-cyan/20 bg-pacman-bg/40 p-4 backdrop-blur"
        role="log"
        aria-live="polite"
        aria-label="Mensagens"
      >
        {messages.length === 0 ? (
          <p className="text-slate-400">A conversa aparecera aqui.</p>
        ) : (
          <div className="flex flex-col">
            {messages.map((message) => (
              <ChatMessage key={message.id} message={message} />
            ))}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      {/* Controles: microfone (web) + input de comando por texto. */}
      <div className="flex items-end gap-3">
        <MicButton />
        <ChatInput onSend={handleSend} disabled={isLoading} />
      </div>
    </section>
  );
}

export default ChatPanel;
