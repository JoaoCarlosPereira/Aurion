// MicButton.tsx — Botao flutuante de microfone para comandos por voz na web (task 16).
// Grava audio via useAudioRecorder e transmite ao backend pelo WebSocket
// /ws/voice-command/{session_id} usando as mensagens audio_start / audio_chunk /
// audio_end (TechSpec 3.2). Exibe feedback visual de gravacao, trata permissao
// negada com modal de instrucoes (TechSpec 10.1) e permite cancelar a gravacao.

import { useCallback, useMemo, useRef, useState } from "react";
import { useAudioRecorder } from "@/hooks/useAudioRecorder";
import { useWebSocket } from "@/hooks/useWebSocket";
import { wsPaths } from "@/services/websocket";
import type { VoiceCommandMessage } from "@/types";

/** Props do botao de microfone. */
export interface MicButtonProps {
  /**
   * Identificador da sessao de voz. Se omitido, um id estavel e gerado
   * automaticamente para a vida do componente.
   */
  sessionId?: string;
}

/** Gera um identificador de sessao aleatorio (com fallback sem crypto). */
function generateSessionId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `web-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

/** Animacao de ondas sonoras exibida durante a gravacao. */
function SoundWaves() {
  // Cinco barras com atrasos diferentes simulam ondas de audio.
  const bars = [0, 1, 2, 3, 4];
  return (
    <span
      className="flex items-end gap-[3px]"
      aria-hidden="true"
      data-testid="sound-waves"
    >
      {bars.map((index) => (
        <span
          key={index}
          className="aurion-mic-wave w-[3px] rounded-full bg-pacman-bg"
          style={{ animationDelay: `${index * 0.12}s` }}
        />
      ))}
    </span>
  );
}

/**
 * Botao flutuante que ativa/desativa a captura de audio e a transmite ao
 * backend via WebSocket.
 */
export function MicButton({ sessionId }: MicButtonProps = {}) {
  // Sessao estavel para toda a vida do componente.
  const resolvedSessionId = useMemo(
    () => sessionId ?? generateSessionId(),
    [sessionId],
  );

  // Flag para distinguir parada normal (envia audio_end) de cancelamento.
  const cancelledRef = useRef(false);

  // Conexao com o endpoint de comando por voz. Conecta apenas ao montar e
  // permanece pronta; o envio so ocorre durante a gravacao.
  const { send, status: wsStatus } = useWebSocket<unknown, VoiceCommandMessage>(
    { path: wsPaths.voiceCommand(resolvedSessionId) },
  );

  // Encaminha cada chunk base64 capturado como mensagem audio_chunk.
  const handleChunk = useCallback(
    (base64Chunk: string) => {
      send({ type: "audio_chunk", data: base64Chunk });
    },
    [send],
  );

  const { isRecording, status, error, permissionDenied, start, stop } =
    useAudioRecorder({ onChunk: handleChunk });

  // Modal de permissao negada (TechSpec 10.1).
  const [showPermissionModal, setShowPermissionModal] = useState(false);

  /** Inicia a gravacao: abre a sessao de audio no servidor e captura. */
  const handleStart = useCallback(async () => {
    cancelledRef.current = false;
    send({ type: "audio_start" });
    await start();
  }, [send, start]);

  /** Para a gravacao normalmente e sinaliza o fim do audio ao servidor. */
  const handleStop = useCallback(() => {
    stop();
    if (!cancelledRef.current) {
      send({ type: "audio_end" });
    }
  }, [stop, send]);

  /** Cancela a gravacao sem enviar audio_end (descarta o comando). */
  const handleCancel = useCallback(() => {
    cancelledRef.current = true;
    stop();
  }, [stop]);

  /** Alterna gravacao; exibe modal se a permissao tiver sido negada. */
  const handleToggle = useCallback(() => {
    if (isRecording) {
      handleStop();
      return;
    }
    if (permissionDenied) {
      setShowPermissionModal(true);
      return;
    }
    void handleStart();
  }, [isRecording, permissionDenied, handleStop, handleStart]);

  // Erro de permissao detectado de forma assincrona apos tentar gravar.
  const hasPermissionError = permissionDenied || showPermissionModal;

  return (
    <div className="relative flex items-center gap-3">
      {/* Animacoes locais (Tailwind v4 nao define keyframes customizados). */}
      <style>{`
        @keyframes aurion-mic-wave {
          0%, 100% { height: 6px; }
          50% { height: 18px; }
        }
        .aurion-mic-wave {
          height: 6px;
          animation: aurion-mic-wave 0.9s ease-in-out infinite;
        }
        @keyframes aurion-mic-ring {
          0% { box-shadow: 0 0 0 0 rgba(52, 211, 255, 0.5); }
          70% { box-shadow: 0 0 0 12px rgba(52, 211, 255, 0); }
          100% { box-shadow: 0 0 0 0 rgba(52, 211, 255, 0); }
        }
        .aurion-mic-recording {
          animation: aurion-mic-ring 1.4s ease-out infinite;
        }
      `}</style>

      <button
        type="button"
        onClick={handleToggle}
        data-testid="mic-button"
        className={[
          "flex h-14 w-14 items-center justify-center rounded-full border-2 transition",
          isRecording
            ? "aurion-mic-recording border-pacman-yellow bg-pacman-yellow text-pacman-bg"
            : "border-cyan bg-pacman-bg text-cyan hover:bg-cyan/10",
        ].join(" ")}
        aria-label={isRecording ? "Parar gravacao" : "Iniciar gravacao"}
        aria-pressed={isRecording}
      >
        {isRecording ? (
          <SoundWaves />
        ) : (
          <span aria-hidden="true" className="text-xl">
            {status === "requesting" ? "…" : "🎙"}
          </span>
        )}
      </button>

      {/* Botao de cancelamento, visivel apenas durante a gravacao. */}
      {isRecording && (
        <button
          type="button"
          onClick={handleCancel}
          data-testid="mic-cancel"
          className="flex h-10 w-10 items-center justify-center rounded-full border border-red-400/60 text-red-300 transition hover:bg-red-400/10"
          aria-label="Cancelar gravacao"
        >
          <span aria-hidden="true">✕</span>
        </button>
      )}

      {/* Indicador textual de gravacao ativa. */}
      {isRecording && (
        <span
          className="text-sm font-semibold text-pacman-yellow"
          role="status"
          data-testid="recording-indicator"
        >
          Gravando{wsStatus !== "open" ? " (reconectando…)" : ""}
        </span>
      )}

      {/* Erro inline nao relacionado a permissao. */}
      {error && !permissionDenied && (
        <span className="text-sm text-red-300" role="alert">
          {error}
        </span>
      )}

      {/* Modal de orientacao quando a permissao do microfone e negada. */}
      {hasPermissionError && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="mic-permission-title"
          data-testid="permission-modal"
        >
          <div className="w-full max-w-md rounded-2xl border border-cyan/30 bg-pacman-bg p-6 text-slate-100 shadow-xl">
            <h2
              id="mic-permission-title"
              className="mb-2 text-lg font-bold text-cyan"
            >
              Microfone bloqueado
            </h2>
            <p className="mb-4 text-sm text-slate-300">
              O acesso ao microfone foi negado. Para usar comandos por voz,
              autorize o microfone nas permissoes do site (icone de cadeado na
              barra de enderecos) e tente novamente.
            </p>
            <button
              type="button"
              onClick={() => setShowPermissionModal(false)}
              className="rounded-lg border border-cyan/40 px-4 py-2 text-sm font-semibold text-cyan transition hover:bg-cyan/10"
            >
              Entendi
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default MicButton;
