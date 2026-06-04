// useAudioRecorder.ts — Hook de gravacao de audio do navegador (task 16).
// Captura audio via MediaDevices.getUserMedia + MediaRecorder, emite cada
// chunk codificado em base64 e trata permissao negada (TechSpec secao 10).
// A assinatura publica e identica ao stub (task 12); apenas o corpo muda.

import { useCallback, useEffect, useRef, useState } from "react";

/** Estado da gravacao de audio. */
export type RecorderStatus = "idle" | "requesting" | "recording" | "error";

/** Opcoes de configuracao do gravador. */
export interface UseAudioRecorderOptions {
  /** Callback para cada chunk de audio capturado (base64). */
  onChunk?: (base64Chunk: string) => void;
  /** Sample rate desejado (padrao 16000, alinhado com o backend). */
  sampleRate?: number;
  /** Intervalo (ms) entre emissoes de chunk do MediaRecorder (padrao 250). */
  timeSliceMs?: number;
}

/** Contrato retornado pelo hook de gravacao. */
export interface UseAudioRecorderResult {
  status: RecorderStatus;
  isRecording: boolean;
  error: string | null;
  /** Indica que a permissao do microfone foi negada pelo navegador. */
  permissionDenied: boolean;
  /** Inicia a captura (solicita permissao de microfone). */
  start: () => Promise<void>;
  /** Para a captura e libera os recursos. */
  stop: () => void;
}

/** Sample rate padrao alinhado ao backend (TechSpec 4.2: 16kHz). */
const DEFAULT_SAMPLE_RATE = 16000;
/** Intervalo padrao de emissao de chunks. */
const DEFAULT_TIME_SLICE_MS = 250;

/**
 * Converte um Blob de audio em string base64 (sem o prefixo data: URL),
 * adequada para o payload `audio_chunk` do WebSocket (TechSpec 3.2).
 */
async function blobToBase64(blob: Blob): Promise<string> {
  const buffer = await blob.arrayBuffer();
  const bytes = new Uint8Array(buffer);
  let binary = "";
  for (let i = 0; i < bytes.length; i += 1) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}

/**
 * Hook de gravacao de audio do navegador.
 *
 * Solicita acesso ao microfone, grava via MediaRecorder e emite cada chunk
 * em base64 atraves de `options.onChunk`. Libera o stream ao parar e ao
 * desmontar o componente.
 */
export function useAudioRecorder(
  options: UseAudioRecorderOptions = {},
): UseAudioRecorderResult {
  const {
    onChunk,
    sampleRate = DEFAULT_SAMPLE_RATE,
    timeSliceMs = DEFAULT_TIME_SLICE_MS,
  } = options;

  const [status, setStatus] = useState<RecorderStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const [permissionDenied, setPermissionDenied] = useState(false);

  // Referencias mutaveis para os recursos de captura (nao disparam re-render).
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  // Mantem o callback mais recente sem recriar `start`.
  const onChunkRef = useRef(onChunk);
  onChunkRef.current = onChunk;

  /** Para o MediaRecorder e encerra todas as tracks do stream. */
  const releaseResources = useCallback((): void => {
    const recorder = mediaRecorderRef.current;
    if (recorder && recorder.state !== "inactive") {
      recorder.stop();
    }
    mediaRecorderRef.current = null;

    const stream = streamRef.current;
    if (stream) {
      stream.getTracks().forEach((track) => track.stop());
    }
    streamRef.current = null;
  }, []);

  const start = useCallback(async (): Promise<void> => {
    // Evita gravacoes concorrentes.
    if (mediaRecorderRef.current) {
      return;
    }

    setError(null);
    setPermissionDenied(false);
    setStatus("requesting");

    // Verifica suporte do navegador as APIs necessarias.
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setStatus("error");
      setError("Captura de audio nao suportada neste navegador.");
      return;
    }

    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
        },
      });
    } catch (err) {
      // Permissao negada ou microfone inacessivel (TechSpec 10.1).
      setStatus("error");
      const name = err instanceof DOMException ? err.name : "";
      if (name === "NotAllowedError" || name === "SecurityError") {
        setPermissionDenied(true);
        setError("Permissao de microfone negada.");
      } else if (name === "NotFoundError" || name === "NotReadableError") {
        setError("Microfone indisponivel ou em uso por outro aplicativo.");
      } else {
        setError("Nao foi possivel acessar o microfone.");
      }
      return;
    }

    streamRef.current = stream;

    let recorder: MediaRecorder;
    try {
      recorder = new MediaRecorder(stream);
    } catch {
      releaseResources();
      setStatus("error");
      setError("Nao foi possivel iniciar a gravacao.");
      return;
    }
    mediaRecorderRef.current = recorder;

    // A cada fatia de tempo, converte o chunk em base64 e o emite.
    recorder.ondataavailable = (event: BlobEvent) => {
      if (event.data && event.data.size > 0) {
        void blobToBase64(event.data).then((base64) => {
          onChunkRef.current?.(base64);
        });
      }
    };

    recorder.onerror = () => {
      setStatus("error");
      setError("Falha durante a gravacao de audio.");
      releaseResources();
    };

    recorder.start(timeSliceMs);
    setStatus("recording");
  }, [sampleRate, timeSliceMs, releaseResources]);

  const stop = useCallback((): void => {
    releaseResources();
    setStatus("idle");
  }, [releaseResources]);

  // Libera recursos ao desmontar o componente (evita vazamento de microfone).
  useEffect(() => {
    return () => {
      releaseResources();
    };
  }, [releaseResources]);

  return {
    status,
    isRecording: status === "recording",
    error,
    permissionDenied,
    start,
    stop,
  };
}
