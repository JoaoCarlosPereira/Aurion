// AudioPlayer.tsx — Reproducao progressiva de audio TTS via WebSocket.
//
// Se `sessionId` e' fornecido, conecta ao /ws/audio/{sessionId} e acumula
// chunks binarios. Se `src` e' fornecido, usa o elemento <audio> nativo
// diretamente (modo simples).

import { useCallback, useEffect, useRef, useState } from "react";
import { wsPaths } from "@/services/websocket";

/** Props do player de audio TTS. */
export interface AudioPlayerProps {
  /** Identificador da sessao (vinculado a /ws/audio/{sessionId}). */
  sessionId?: string;
  /** URL direta de audio (modo simples, sem WebSocket). */
  src?: string | null;
  /** Callback quando o audio termina de reproduzir. */
  onEnd?: () => void;
  /** Callback quando um novo chunk de audio e' recebido. */
  onChunk?: (chunk: Uint8Array) => void;
}

/**
 * Player de audio TTS com streaming progressivo via WebSocket.
 *
 * Se `sessionId` e' fornecido, conecta ao /ws/audio/{sessionId} e acumula
 * chunks binarios. Se `src` e' fornecido, usa o elemento <audio> nativo
 * diretamente (modo simples).
 */
export function AudioPlayer({ sessionId, src, onEnd, onChunk }: AudioPlayerProps) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [bufferedBytes, setBufferedBytes] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const audioRef = useRef<HTMLAudioElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const chunksRef = useRef<Uint8Array[]>([]);
  const animFrameRef = useRef<number | null>(null);
  const cleanupWaveformRef = useRef<(() => void) | null>(null);

  // Acumula chunks e atualiza o Blob URL do audio.
  const appendChunk = useCallback(
    (chunk: Uint8Array) => {
      chunksRef.current.push(chunk);
      setBufferedBytes(chunksRef.current.reduce((sum, c) => sum + c.length, 0));

      // Reconstroi o Blob URL e atualiza o audio element.
      const blob = new Blob(chunksRef.current as BlobPart[], {
        type: "audio/mpeg",
      });
      const url = URL.createObjectURL(blob);
      if (audioRef.current) {
        audioRef.current.src = url;
        if (!isPlaying) {
          void audioRef.current.play().catch(() => {
            // Autoplay bloqueado.
          });
        }
      }

      // Visualizacao do waveform via AnalyserNode.
      if (canvasRef.current && audioRef.current) {
        try {
          // Cancela waveform anterior.
          if (cleanupWaveformRef.current) {
            cleanupWaveformRef.current();
          }
          cleanupWaveformRef.current = createWaveform(canvasRef.current, audioRef.current);
        } catch {
          // Visualizacao opcional.
        }
      }

      onChunk?.(chunk);
    },
    [isPlaying, onChunk],
  );

  useEffect(() => {
    if (!sessionId) {
      // Modo simples com src.
      const audio = audioRef.current;
      if (!audio) return;
      if (src) {
        audio.src = src;
      }
      const onPlay = () => setIsPlaying(true);
      const onPause = () => setIsPlaying(false);
      const onEnded = () => {
        setIsPlaying(false);
        onEnd?.();
      };
      audio.addEventListener("play", onPlay);
      audio.addEventListener("pause", onPause);
      audio.addEventListener("ended", onEnded);
      return () => {
        audio.removeEventListener("play", onPlay);
        audio.removeEventListener("pause", onPause);
        audio.removeEventListener("ended", onEnded);
        if (animFrameRef.current) {
          cancelAnimationFrame(animFrameRef.current);
        }
        if (cleanupWaveformRef.current) {
          cleanupWaveformRef.current();
        }
      };
    }

    // Modo WebSocket streaming.
    let ws: WebSocket | null = null;
    let disposed = false;

    const connect = () => {
      ws = new WebSocket(wsPaths.audio(sessionId!));
      ws.binaryType = "arraybuffer";

      ws.onopen = () => {
        setError(null);
      };

      ws.onmessage = (event) => {
        if (event.data instanceof ArrayBuffer) {
          const chunk = new Uint8Array(event.data);
          appendChunk(chunk);
        }
      };

      ws.onclose = () => {
        if (!disposed) {
          setTimeout(connect, 2000);
        }
      };

      ws.onerror = () => {
        setError("Falha na conexao de audio.");
      };
    };

    connect();

    const onPlay = () => setIsPlaying(true);
    const onPause = () => setIsPlaying(false);
    const onEnded = () => {
      setIsPlaying(false);
      onEnd?.();
    };

    const audio = audioRef.current;
    if (audio) {
      audio.addEventListener("play", onPlay);
      audio.addEventListener("pause", onPause);
      audio.addEventListener("ended", onEnded);
    }

    return () => {
      disposed = true;
      if (ws) ws.close();
      if (audio) {
        audio.removeEventListener("play", onPlay);
        audio.removeEventListener("pause", onPause);
        audio.removeEventListener("ended", onEnded);
      }
      if (animFrameRef.current) {
        cancelAnimationFrame(animFrameRef.current);
      }
      if (cleanupWaveformRef.current) {
        cleanupWaveformRef.current();
      }
    };
  }, [sessionId, appendChunk, onEnd, src]);

  const handleToggle = useCallback(() => {
    const audio = audioRef.current;
    if (!audio) return;
    if (audio.paused) {
      void audio.play();
    } else {
      audio.pause();
    }
  }, []);

  const handleSeek = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const audio = audioRef.current;
      if (!audio) return;
      audio.currentTime = parseFloat(e.target.value);
    },
    []
  );

  return (
    <div className="flex w-full flex-col gap-2 rounded-xl border border-cyan/20 bg-pacman-bg/40 p-3">
      <canvas
        ref={canvasRef}
        width={400}
        height={48}
        className="h-12 w-full rounded-lg bg-pacman-bg/60"
        aria-label="Waveform do audio TTS"
      />

      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={handleToggle}
          disabled={bufferedBytes === 0 && !src}
          className="flex h-10 w-10 items-center justify-center rounded-full bg-cyan/20 text-cyan transition hover:bg-cyan/30 disabled:cursor-not-allowed disabled:opacity-50"
          aria-label={isPlaying ? "Pausar" : "Reproduzir"}
        >
          {isPlaying ? "⏸" : "▶"}
        </button>

        <input
          type="range"
          min={0}
          max={audioRef.current?.duration || 0}
          defaultValue={0}
          onChange={handleSeek}
          className="flex-1 accent-cyan"
          aria-label="Tempo de reproducao"
        />

        <span className="text-xs text-slate-400">
          {bufferedBytes > 0 ? `${Math.round(bufferedBytes / 1024)} KB` : src ? "Audio pronto" : "Aguardando audio..."}
        </span>
      </div>

      {error && (
        <span className="text-xs text-red-300" role="alert">
          {error}
        </span>
      )}
    </div>
  );
}

/** Cria waveform visual no canvas usando AnalyserNode FFT. */
function createWaveform(canvas: HTMLCanvasElement, audioEl: HTMLAudioElement): () => void {
  let currentFrame: number | null = null;
  const ctx2d = canvas.getContext("2d");
  if (!ctx2d) return () => {};

  try {
    const AC = (window.AudioContext ||
      (window as unknown as { webkitAudioContext: typeof AudioContext })
        .webkitAudioContext) as typeof AudioContext;
    const ctx = new AC();
    const source = ctx.createMediaElementSource(audioEl);
    const analyser = ctx.createAnalyser();
    source.connect(analyser);
    analyser.connect(ctx.destination);

    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);

    const draw = () => {
      analyser.getByteFrequencyData(dataArray);
      ctx2d.clearRect(0, 0, canvas.width, canvas.height);

      const barWidth = canvas.width / bufferLength * 2;
      let x = 0;
      for (let i = 0; i < bufferLength; i++) {
        const barHeight = (dataArray[i] / 255) * canvas.height;
        ctx2d.fillStyle = `rgba(52, 211, 255, ${0.3 + (dataArray[i] / 255) * 0.7})`;
        ctx2d.fillRect(x, canvas.height - barHeight, barWidth - 1, barHeight);
        x += barWidth;
        if (x > canvas.width) break;
      }

      currentFrame = requestAnimationFrame(draw);
    };

    draw();
    return () => {
      if (currentFrame != null) cancelAnimationFrame(currentFrame);
      ctx.close();
    };
  } catch {
    return () => {};
  }
}

export default AudioPlayer;
