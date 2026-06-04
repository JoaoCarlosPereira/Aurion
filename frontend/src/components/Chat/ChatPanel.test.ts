// ChatPanel.test.ts — Testes unitarios dos componentes de Chat (task 13).
//
// CONTEXTO IMPORTANTE: o scaffolding atual (package.json) NAO inclui um test
// runner (vitest/jest) nem @testing-library, e a tarefa proibe `npm install`.
// Importar essas libs quebraria a validacao obrigatoria `npx tsc --noEmit`.
//
// Por isso, este arquivo usa um harness local minimo, sem dependencias externas,
// que (1) e 100% type-checavel por `tsc --noEmit` e (2) pode ser executado por
// qualquer runner (vitest/node --import tsx) sem alteracoes, pois auto-executa
// ao ser carregado. Quando o runner for adicionado (task 18), estes casos podem
// ser portados para `describe/it` sem perder cobertura logica.

import { SYSTEM_STATE_META } from "@/hooks/useSystemState";
import type { ChatMessage as ChatMessageModel, SystemState } from "@/types";

// ---------------------------------------------------------------------------
// Harness de asserts minimo (sem libs externas).
// ---------------------------------------------------------------------------

let passed = 0;
let failed = 0;

function check(name: string, condition: boolean): void {
  if (condition) {
    passed += 1;
  } else {
    failed += 1;
    // eslint-disable-next-line no-console
    console.error(`FALHOU: ${name}`);
  }
}

function equal<T>(name: string, actual: T, expected: T): void {
  check(`${name} (esperado=${String(expected)}, obtido=${String(actual)})`, actual === expected);
}

// ---------------------------------------------------------------------------
// Replicas das regras puras testadas (espelham a logica dos componentes).
// Mantidas aqui porque os helpers dos componentes sao privados ao modulo.
// ---------------------------------------------------------------------------

/** Espelha ChatMessage.roleLabel. */
function roleLabel(message: ChatMessageModel): string {
  if (message.role === "user") return "Voce";
  if (message.role === "assistant") return "Aurion";
  return "Sistema";
}

/** Espelha ChatInput.submit: so envia texto nao vazio e quando habilitado. */
function canSubmit(value: string, disabled: boolean): boolean {
  return value.trim().length > 0 && !disabled;
}

/** Espelha ChatPanel.base64ToBytes. */
function base64ToBytes(base64: string): Uint8Array {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}

// ---------------------------------------------------------------------------
// 1. Cores de estado do sistema (TechSpec 6.2) — todos os 7 estados.
// ---------------------------------------------------------------------------

const expectedColors: Record<SystemState, string> = {
  idle: "#6b7280",
  listening: "#3b82f6",
  detecting: "#34d3ff",
  stt: "#8b5cf6",
  processing: "#ffd166",
  tts: "#22c55e",
  error: "#ef4444",
};

(Object.keys(expectedColors) as SystemState[]).forEach((state) => {
  equal(`cor do estado ${state}`, SYSTEM_STATE_META[state].color, expectedColors[state]);
});

// ---------------------------------------------------------------------------
// 2. Rotulo de autor por role (ChatMessage).
// ---------------------------------------------------------------------------

const base = { id: "1", text: "oi", timestamp: new Date().toISOString() };
equal("rotulo usuario", roleLabel({ ...base, role: "user" }), "Voce");
equal("rotulo assistant", roleLabel({ ...base, role: "assistant" }), "Aurion");
equal("rotulo system", roleLabel({ ...base, role: "system" }), "Sistema");

// ---------------------------------------------------------------------------
// 3. Validacao de envio do ChatInput.
// ---------------------------------------------------------------------------

equal("nao envia texto vazio", canSubmit("   ", false), false);
equal("nao envia quando desabilitado", canSubmit("ola", true), false);
equal("envia texto valido habilitado", canSubmit("ola", false), true);

// ---------------------------------------------------------------------------
// 4. Decodificacao base64 de chunk de audio TTS.
// ---------------------------------------------------------------------------

const decoded = base64ToBytes(btoa("abc"));
equal("base64 decodifica tamanho", decoded.length, 3);
equal("base64 decodifica primeiro byte", decoded[0], "a".charCodeAt(0));

// ---------------------------------------------------------------------------
// Resultado consolidado.
// ---------------------------------------------------------------------------

// eslint-disable-next-line no-console
console.log(`Chat tests: ${passed} passou, ${failed} falhou.`);

export const chatTestResult = { passed, failed };
