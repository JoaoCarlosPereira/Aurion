// STTConfig.tsx — Sub-painel de configuracao do servico de Speech-to-Text.
// Edita engine, model, language, threads, beam_size e max_context (TechSpec 4.2 / 5.3),
// valida faixas numericas e testa a conexao via POST /api/test/stt.

import { useEffect, useState } from "react";
import type { STTConfig as STTConfigType } from "@/types";
import { useAurionAPI } from "@/hooks/useAurionAPI";
import {
  Field,
  NumberInput,
  SectionCard,
  SelectInput,
  TestButton,
  TextInput,
  initialTestState,
  validateNumberRange,
  type InlineTestState,
} from "@/components/Settings/settingsShared";

/** Props do sub-painel STT. */
export interface STTConfigProps {
  value: STTConfigType;
  onChange: (value: STTConfigType) => void;
  onValidityChange?: (valid: boolean) => void;
}

/** Opcoes de idioma suportadas (foco em PT-BR conforme TechSpec 5.3). */
const LANGUAGE_OPTIONS = [
  { value: "pt-BR", label: "Portugues (Brasil)" },
  { value: "pt", label: "Portugues" },
  { value: "en", label: "Ingles" },
] as const;

/** Formulario de configuracao do servico STT. */
export function STTConfig({ value, onChange, onValidityChange }: STTConfigProps) {
  const apiClient = useAurionAPI();
  const [test, setTest] = useState<InlineTestState>(initialTestState);

  // Validacao das faixas numericas (TechSpec 5.3).
  const threadsError = validateNumberRange(value.threads, 1, 32, {
    integer: true,
  });
  const beamSizeError = validateNumberRange(value.beam_size, 1, 10, {
    integer: true,
  });
  // max_context aceita -1 (sem limite) ate valores positivos.
  const maxContextError = validateNumberRange(value.max_context, -1, 16384, {
    integer: true,
  });
  const valid =
    threadsError === null &&
    beamSizeError === null &&
    maxContextError === null;

  useEffect(() => {
    onValidityChange?.(valid);
  }, [valid, onValidityChange]);

  /** Dispara o teste de conexao do STT. */
  async function handleTest() {
    setTest({ status: "loading", message: null });
    try {
      const result = await apiClient.testSTT();
      setTest({
        status: result.ok ? "success" : "error",
        message: result.message,
      });
    } catch {
      setTest({
        status: "error",
        message: "Falha ao testar o servico STT.",
      });
    }
  }

  return (
    <SectionCard
      title="STT (Speech-to-Text)"
      description="Reconhecimento de voz local via whisper.cpp."
    >
      <div className="grid gap-4 md:grid-cols-2">
        <Field label="Engine" htmlFor="stt-engine">
          <TextInput
            id="stt-engine"
            value={value.engine}
            placeholder="whisper.cpp"
            onChange={(engine) => onChange({ ...value, engine })}
          />
        </Field>

        <Field label="Modelo" htmlFor="stt-model">
          <TextInput
            id="stt-model"
            value={value.model}
            placeholder="ggml-base-q4"
            onChange={(model) => onChange({ ...value, model })}
          />
        </Field>

        <Field label="Idioma" htmlFor="stt-language">
          <SelectInput
            id="stt-language"
            value={value.language}
            options={LANGUAGE_OPTIONS}
            onChange={(language) => onChange({ ...value, language })}
          />
        </Field>

        <Field
          label="Threads"
          htmlFor="stt-threads"
          error={threadsError}
          hint="1 a 32"
        >
          <NumberInput
            id="stt-threads"
            value={value.threads}
            min={1}
            max={32}
            step={1}
            error={threadsError}
            onChange={(threads) => onChange({ ...value, threads })}
          />
        </Field>

        <Field
          label="Beam size"
          htmlFor="stt-beam-size"
          error={beamSizeError}
          hint="1 a 10 (1 = menor latencia)"
        >
          <NumberInput
            id="stt-beam-size"
            value={value.beam_size}
            min={1}
            max={10}
            step={1}
            error={beamSizeError}
            onChange={(beam_size) => onChange({ ...value, beam_size })}
          />
        </Field>

        <Field
          label="Contexto maximo"
          htmlFor="stt-max-context"
          error={maxContextError}
          hint="-1 para sem limite"
        >
          <NumberInput
            id="stt-max-context"
            value={value.max_context}
            min={-1}
            step={1}
            error={maxContextError}
            onChange={(max_context) => onChange({ ...value, max_context })}
          />
        </Field>
      </div>

      <TestButton label="Testar STT" state={test} onTest={handleTest} />
    </SectionCard>
  );
}

export default STTConfig;
