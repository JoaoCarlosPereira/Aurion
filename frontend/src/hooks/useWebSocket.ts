// useWebSocket.ts — Hook generico para gerenciar uma conexao WebSocket tipada.
// Cuida do ciclo de vida (connect/close) e expoe status e funcao de envio.

import { useCallback, useEffect, useRef, useState } from "react";
import {
  AurionWebSocket,
  type WebSocketHandlers,
  type WSStatus,
} from "@/services/websocket";

/** Opcoes do hook useWebSocket. */
export interface UseWebSocketOptions<TIncoming> {
  /** Path do endpoint (ex: "/ws/status"). */
  path: string;
  /** Conectar automaticamente ao montar (padrao: true). */
  enabled?: boolean;
  /** Callback para cada mensagem recebida. */
  onMessage?: (data: TIncoming) => void;
}

/** Valor de retorno do hook useWebSocket. */
export interface UseWebSocketResult<TOutgoing> {
  status: WSStatus;
  send: (message: TOutgoing) => void;
  connect: () => void;
  disconnect: () => void;
}

/**
 * Gerencia uma conexao WebSocket reativa.
 *
 * @typeParam TIncoming Tipo das mensagens recebidas.
 * @typeParam TOutgoing Tipo das mensagens enviadas.
 */
export function useWebSocket<TIncoming = unknown, TOutgoing = unknown>(
  options: UseWebSocketOptions<TIncoming>,
): UseWebSocketResult<TOutgoing> {
  const { path, enabled = true, onMessage } = options;
  const [status, setStatus] = useState<WSStatus>("closed");
  const clientRef = useRef<AurionWebSocket<TIncoming, TOutgoing> | null>(null);
  // Mantem o callback mais recente sem recriar a conexao.
  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;

  useEffect(() => {
    const handlers: WebSocketHandlers<TIncoming> = {
      onMessage: (data) => onMessageRef.current?.(data),
      onStatusChange: setStatus,
    };
    const client = new AurionWebSocket<TIncoming, TOutgoing>(path, handlers);
    clientRef.current = client;

    if (enabled) {
      client.connect();
    }

    return () => {
      client.close();
      clientRef.current = null;
    };
  }, [path, enabled]);

  const send = useCallback((message: TOutgoing) => {
    clientRef.current?.send(message);
  }, []);

  const connect = useCallback(() => {
    clientRef.current?.connect();
  }, []);

  const disconnect = useCallback(() => {
    clientRef.current?.close();
  }, []);

  return { status, send, connect, disconnect };
}
