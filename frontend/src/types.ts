// types.ts — Contrato compartilhado de tipos do Aurion (TechSpec secao 3).
// Estes tipos espelham os modelos Pydantic do backend e os payloads de WebSocket.
// Codigo/identificadores em ingles conforme convencao React/TS.

// ---------------------------------------------------------------------------
// Estados do sistema (TechSpec 6.2)
// ---------------------------------------------------------------------------

/** Estado de alto nivel do pipeline de voz, refletido na UI. */
export type SystemState =
  | "idle"
  | "listening"
  | "detecting"
  | "stt"
  | "processing"
  | "tts"
  | "error";

/** Canal de origem de uma interacao. */
export type Channel = "local" | "web";

/** Status final de uma interacao persistida. */
export type InteractionStatus = "success" | "error" | "timeout";

// ---------------------------------------------------------------------------
// Interacao (TechSpec 3.3 / 4.1)
// ---------------------------------------------------------------------------

/** Registro de uma interacao (entrada do usuario + resposta do Hermes). */
export interface Interaction {
  id: string;
  /** ISO 8601 timestamp. */
  timestamp: string;
  channel: Channel;
  input_text: string;
  output_text: string | null;
  output_audio_url: string | null;
  duration_ms: number | null;
  status: InteractionStatus;
  error_message: string | null;
}

// ---------------------------------------------------------------------------
// Configuracao (TechSpec 3.3 / 4.2)
// ---------------------------------------------------------------------------

/** Configuracao de conexao com o Hermes Agent. */
export interface HermesConfig {
  endpoint: string;
  auth_token: string;
}

/** Configuracao do servico de Speech-to-Text. */
export interface STTConfig {
  engine: string;
  model: string;
  language: string;
  threads: number;
  beam_size: number;
  max_context: number;
}

/** Parametros enviados ao endpoint de TTS externo. */
export interface TTSExternalParams {
  input: string;
  voice: string;
  speed: number;
}

/** Configuracao do TTS externo (opcional, com fallback para edge-tts). */
export interface TTSExternalConfig {
  enabled: boolean;
  endpoint: string;
  api_key: string;
  params: TTSExternalParams;
  format: string;
  timeout: number;
  /** Buffer de pre-carregamento em ms (padrao 500). */
  stream_buffer_ms?: number;
  /** Headers HTTP adicionais (ex: Authorization). */
  headers?: Record<string, string>;
}

/** Configuracao do servico de Text-to-Speech. */
export interface TTSConfig {
  engine: string;
  voice: string;
  rate: number;
  volume: number;
  pitch?: number;
  external: TTSExternalConfig;
}

/** Configuracao da deteccao de wake word ("Aurion"). */
export interface WakeWordConfig {
  engine: string;
  sensitivity: number;
  keyword: string;
}

/** Configuracao de captura de audio (PyAudio). */
export interface AudioConfig {
  sample_rate: number;
  channels: number;
  chunk_size: number;
  silence_threshold: number;
  wake_word_timeout: number;
}

/** Configuracao agregada da aplicacao (raiz do config.json). */
export interface AppConfig {
  hermes: HermesConfig;
  stt: STTConfig;
  tts: TTSConfig;
  wake_word: WakeWordConfig;
  audio: AudioConfig;
}

// ---------------------------------------------------------------------------
// Respostas da API REST (TechSpec 3.1 / 10.2)
// ---------------------------------------------------------------------------

/** Resposta do POST /api/command. */
export interface CommandResponse {
  id: string;
  status: string;
}

/** Resultado de um teste de conexao (/api/test/*). */
export interface TestResult {
  ok: boolean;
  message: string;
  details?: Record<string, unknown> | null;
}

/** Estrutura padrao de erro da API (TechSpec 10.2). */
export interface APIError {
  code: string;
  message: string;
  details?: Record<string, unknown> | null;
}

/** Parametros de consulta do historico (TechSpec 3.1). */
export interface HistoryQuery {
  limit?: number;
  offset?: number;
  search?: string;
}

// ---------------------------------------------------------------------------
// Mensagens de WebSocket (TechSpec 3.2)
// ---------------------------------------------------------------------------

/** Mensagem recebida em /ws/status (Server -> Client). */
export interface StatusMessage {
  state: SystemState;
  message?: string;
}

/** Chunk de audio recebido em /ws/audio (Server -> Client). */
export interface AudioChunkMessage {
  type: "audio_chunk";
  /** Audio codificado em base64. */
  data: string;
}

/** Mensagens enviadas pelo cliente em /ws/voice-command (Client -> Server). */
export type VoiceCommandMessage =
  | { type: "audio_start" }
  | { type: "audio_chunk"; data: string }
  | { type: "audio_end" };

// ---------------------------------------------------------------------------
// Mensagens de chat (estado local da UI)
// ---------------------------------------------------------------------------

/** Autor de uma mensagem no painel de chat. */
export type ChatRole = "user" | "assistant" | "system";

/** Mensagem exibida no painel de chat (estado de UI, nao persistido). */
export interface ChatMessage {
  id: string;
  role: ChatRole;
  text: string;
  /** ISO 8601 timestamp. */
  timestamp: string;
  /** URL de audio TTS associado, quando houver. */
  audioUrl?: string | null;
  /** Indica se a mensagem ainda esta sendo processada. */
  pending?: boolean;
  /** Indica se a mensagem representa um erro. */
  error?: boolean;
}
