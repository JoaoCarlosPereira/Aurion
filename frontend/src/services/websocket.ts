// websocket.ts — Cliente WebSocket reutilizavel para os endpoints do Aurion
// (TechSpec 3.2): /ws/status, /ws/audio/{session_id}, /ws/voice-command/{session_id}.
// Implementa auto-reconnect com backoff exponencial (TechSpec 10.1, max 5 tentativas).

export type WSStatus = "connecting" | "open" | "closed" | "error";

/** Callbacks de ciclo de vida de uma conexao WebSocket. */
export interface WebSocketHandlers<TIncoming> {
  /** Chamado a cada mensagem JSON valida recebida. */
  onMessage?: (data: TIncoming) => void;
  /** Chamado quando a conexao abre. */
  onOpen?: () => void;
  /** Chamado quando a conexao fecha. */
  onClose?: (event: CloseEvent) => void;
  /** Chamado em erro de transporte ou parse. */
  onError?: (error: unknown) => void;
  /** Chamado a cada mudanca de status (util para indicadores na UI). */
  onStatusChange?: (status: WSStatus) => void;
}

const MAX_RECONNECT_ATTEMPTS = 5;
const BASE_RECONNECT_DELAY_MS = 500;

/**
 * Resolve a URL absoluta de um path de WebSocket relativa a origem atual,
 * respeitando o esquema (ws/wss). Em dev o proxy do Vite encaminha /ws.
 */
export function resolveWebSocketUrl(path: string): string {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const normalized = path.startsWith("/") ? path : `/${path}`;
  return `${protocol}//${window.location.host}${normalized}`;
}

/**
 * Conexao WebSocket tipada com reconexao automatica.
 *
 * @typeParam TIncoming Tipo das mensagens recebidas (Server -> Client).
 * @typeParam TOutgoing Tipo das mensagens enviadas (Client -> Server).
 */
export class AurionWebSocket<TIncoming = unknown, TOutgoing = unknown> {
  private socket: WebSocket | null = null;
  private reconnectAttempts = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private manuallyClosed = false;

  constructor(
    private readonly path: string,
    private readonly handlers: WebSocketHandlers<TIncoming> = {},
  ) {}

  /** Abre a conexao (idempotente enquanto ja conectado). */
  connect(): void {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      return;
    }
    this.manuallyClosed = false;
    this.handlers.onStatusChange?.("connecting");

    const url = resolveWebSocketUrl(this.path);
    const socket = new WebSocket(url);
    this.socket = socket;

    socket.onopen = () => {
      this.reconnectAttempts = 0;
      this.handlers.onStatusChange?.("open");
      this.handlers.onOpen?.();
    };

    socket.onmessage = (event: MessageEvent) => {
      try {
        const parsed = JSON.parse(event.data as string) as TIncoming;
        this.handlers.onMessage?.(parsed);
      } catch (error) {
        this.handlers.onError?.(error);
      }
    };

    socket.onerror = (event) => {
      this.handlers.onStatusChange?.("error");
      this.handlers.onError?.(event);
    };

    socket.onclose = (event: CloseEvent) => {
      this.handlers.onStatusChange?.("closed");
      this.handlers.onClose?.(event);
      if (!this.manuallyClosed) {
        this.scheduleReconnect();
      }
    };
  }

  /** Agenda uma tentativa de reconexao com backoff exponencial. */
  private scheduleReconnect(): void {
    if (this.reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
      return;
    }
    const delay = BASE_RECONNECT_DELAY_MS * 2 ** this.reconnectAttempts;
    this.reconnectAttempts += 1;
    this.reconnectTimer = setTimeout(() => this.connect(), delay);
  }

  /** Envia uma mensagem JSON ao servidor (quando a conexao esta aberta). */
  send(message: TOutgoing): void {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(message));
    }
  }

  /** Fecha a conexao e cancela qualquer reconexao pendente. */
  close(): void {
    this.manuallyClosed = true;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.socket?.close();
    this.socket = null;
  }

  /** Indica se a conexao esta aberta. */
  get isOpen(): boolean {
    return this.socket?.readyState === WebSocket.OPEN;
  }
}

/** Endpoints de WebSocket conhecidos (TechSpec 3.2). */
export const wsPaths = {
  status: () => "/ws/status",
  audio: (sessionId: string) => `/ws/audio/${sessionId}`,
  voiceCommand: (sessionId: string) => `/ws/voice-command/${sessionId}`,
};
