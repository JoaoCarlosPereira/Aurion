// api.ts — Wrapper axios para todos os endpoints REST do backend (TechSpec 3.1).
// O baseURL "/api" e servido pelo proxy do Vite em dev e pelo FastAPI em producao.

import axios, { type AxiosInstance } from "axios";
import type {
  AppConfig,
  CommandResponse,
  HistoryQuery,
  Interaction,
  TestResult,
} from "@/types";

/** Instancia axios compartilhada apontando para o prefixo /api. */
export const httpClient: AxiosInstance = axios.create({
  baseURL: "/api",
  headers: { "Content-Type": "application/json" },
  timeout: 30_000,
});

// ---------------------------------------------------------------------------
// Configuracoes
// ---------------------------------------------------------------------------

/** GET /api/config — retorna todas as configuracoes. */
async function getConfig(): Promise<AppConfig> {
  const { data } = await httpClient.get<AppConfig>("/config");
  return data;
}

/** PUT /api/config — atualiza configuracoes (parcial ou total). */
async function updateConfig(config: Partial<AppConfig>): Promise<AppConfig> {
  const { data } = await httpClient.put<AppConfig>("/config", config);
  return data;
}

// ---------------------------------------------------------------------------
// Testes de conexao (/api/test/*)
// ---------------------------------------------------------------------------

/** POST /api/test/hermes — testa conexao com o Hermes Agent. */
async function testHermes(): Promise<TestResult> {
  const { data } = await httpClient.post<TestResult>("/test/hermes");
  return data;
}

/** POST /api/test/stt — testa conexao com o servico STT. */
async function testSTT(): Promise<TestResult> {
  const { data } = await httpClient.post<TestResult>("/test/stt");
  return data;
}

/** POST /api/test/tts — testa conexao com o TTS (edge-tts ou externo). */
async function testTTS(): Promise<TestResult> {
  const { data } = await httpClient.post<TestResult>("/test/tts");
  return data;
}

// ---------------------------------------------------------------------------
// Historico
// ---------------------------------------------------------------------------

/** GET /api/history — lista interacoes paginadas com busca opcional. */
async function getHistory(query: HistoryQuery = {}): Promise<Interaction[]> {
  const { data } = await httpClient.get<Interaction[]>("/history", {
    params: {
      limit: query.limit ?? 50,
      offset: query.offset ?? 0,
      search: query.search,
    },
  });
  return data;
}

/** GET /api/history/{id} — retorna uma interacao especifica. */
async function getInteraction(id: string): Promise<Interaction> {
  const { data } = await httpClient.get<Interaction>(`/history/${id}`);
  return data;
}

/** DELETE /api/history — limpa todo o historico. */
async function clearHistory(): Promise<void> {
  await httpClient.delete("/history");
}

// ---------------------------------------------------------------------------
// Comandos
// ---------------------------------------------------------------------------

/** POST /api/command — envia comando por texto ao Hermes. */
async function sendCommand(message: string): Promise<CommandResponse> {
  const { data } = await httpClient.post<CommandResponse>("/command", {
    message,
  });
  return data;
}

/** GET /api/command/{id} — consulta status/resposta de um comando. */
async function getCommand(id: string): Promise<Interaction> {
  const { data } = await httpClient.get<Interaction>(`/command/${id}`);
  return data;
}

/** Conjunto de operacoes da API REST do Aurion. */
export const api = {
  getConfig,
  updateConfig,
  testHermes,
  testSTT,
  testTTS,
  getHistory,
  getInteraction,
  clearHistory,
  sendCommand,
  getCommand,
};

export type AurionAPI = typeof api;
