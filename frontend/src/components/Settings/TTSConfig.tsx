// TTSConfig.tsx — Sub-painel de configuracao do servico de Text-to-Speech.
// Edita voz, rate, volume, pitch e o sub-bloco de TTS externo (TechSpec 4.2 / 5.4),
// lista as vozes PT-BR disponiveis e testa via POST /api/test/tts.

import { useEffect, useMemo, useState } from "react";
import type { TTSConfig as TTSConfigType } from "@/types";
import { useAurionAPI } from "@/hooks/useAurionAPI";
import {
  CheckboxInput,
  Field,
  NumberInput,
  SectionCard,
  SelectInput,
  TestButton,
  TextInput,
  initialTestState,
  validateNumberRange,
  validatePositive,
  validateUrl,
  type InlineTestState,
} from "@/components/Settings/settingsShared";

/** Props do sub-painel TTS. */
export interface TTSConfigProps {
  value: TTSConfigType;
  onChange: (value: TTSConfigType) => void;
  onValidityChange?: (valid: boolean) => void;
}

/**
 * Vozes PT-BR disponiveis no edge-tts (TechSpec 5.4).
 * Exportadas para reuso/teste do listing de vozes (requisito 9).
 */
export const PT_BR_VOICES = [
  { value: "pt-BR-FabioNeural", label: "Fabio (masculina)" },
  { value: "pt-BR-FranciscaNeural", label: "Francisca (feminina)" },
  { value: "pt-BR-AntonioNeural", label: "Antonio (masculina)" },
] as const;

/** Formulario de configuracao do servico TTS. */
export function TTSConfig({ value, onChange, onValidityChange }: TTSConfigProps) {
  const apiClient = useAurionAPI();
  const [test, setTest] = useState<InlineTestState>(initialTestState);

  const external = value.external;

  // Validacao dos parametros do edge-tts.
  const rateError = validateNumberRange(value.rate, -100, 100, {
    integer: true,
  });
  const volumeError = validateNumberRange(value.volume, 0, 100, {
    integer: true,
  });
  const pitchError =
    value.pitch === undefined
      ? null
      : validateNumberRange(value.pitch, -100, 100, { integer: true });

  // Validacao do TTS externo: so exige campos quando habilitado.
  const externalEndpointError = external.enabled
    ? validateUrl(external.endpoint, true)
    : null;
  const externalTimeoutError = external.enabled
    ? validatePositive(external.timeout, { integer: true })
    : null;
  const externalSpeedError = external.enabled
    ? validateNumberRange(external.params.speed, 0.5, 2.0)
    : null;

  const valid = useMemo(
    () =>
      rateError === null &&
      volumeError === null &&
      pitchError === null &&
      externalEndpointError === null &&
      externalTimeoutError === null &&
      externalSpeedError === null,
    [
      rateError,
      volumeError,
      pitchError,
      externalEndpointError,
      externalTimeoutError,
      externalSpeedError,
    ],
  );

  useEffect(() => {
    onValidityChange?.(valid);
  }, [valid, onValidityChange]);

  /** Dispara o teste de conexao do TTS (edge-tts ou externo, conforme config). */
  async function handleTest() {
    setTest({ status: "loading", message: null });
    try {
      const result = await apiClient.testTTS();
      setTest({
        status: result.ok ? "success" : "error",
        message: result.message,
      });
    } catch {
      setTest({
        status: "error",
        message: "Falha ao testar o servico TTS.",
      });
    }
  }

  /** Atualiza um campo do sub-bloco external preservando o restante. */
  function patchExternal(patch: Partial<TTSConfigType["external"]>) {
    onChange({ ...value, external: { ...external, ...patch } });
  }

  return (
    <SectionCard
      title="TTS (Text-to-Speech)"
      description="Sintese de voz padrao via edge-tts, com TTS externo opcional."
    >
      <div className="grid gap-4 md:grid-cols-2">
        <Field label="Engine" htmlFor="tts-engine">
          <TextInput
            id="tts-engine"
            value={value.engine}
            placeholder="edge-tts"
            onChange={(engine) => onChange({ ...value, engine })}
          />
        </Field>

        <Field label="Voz" htmlFor="tts-voice" hint="Vozes PT-BR disponiveis">
          <SelectInput
            id="tts-voice"
            value={value.voice}
            options={PT_BR_VOICES}
            onChange={(voice) => onChange({ ...value, voice })}
          />
        </Field>

        <Field
          label="Velocidade (rate)"
          htmlFor="tts-rate"
          error={rateError}
          hint="-100 a 100"
        >
          <NumberInput
            id="tts-rate"
            value={value.rate}
            min={-100}
            max={100}
            step={1}
            error={rateError}
            onChange={(rate) => onChange({ ...value, rate })}
          />
        </Field>

        <Field
          label="Volume"
          htmlFor="tts-volume"
          error={volumeError}
          hint="0 a 100"
        >
          <NumberInput
            id="tts-volume"
            value={value.volume}
            min={0}
            max={100}
            step={1}
            error={volumeError}
            onChange={(volume) => onChange({ ...value, volume })}
          />
        </Field>

        <Field
          label="Pitch"
          htmlFor="tts-pitch"
          error={pitchError}
          hint="-100 a 100 (opcional)"
        >
          <NumberInput
            id="tts-pitch"
            value={value.pitch ?? 0}
            min={-100}
            max={100}
            step={1}
            error={pitchError}
            onChange={(pitch) => onChange({ ...value, pitch })}
          />
        </Field>
      </div>

      {/* Sub-bloco de TTS externo (TechSpec 5.4). */}
      <div className="flex flex-col gap-4 rounded-xl border border-cyan/15 bg-pacman-bg/40 p-3">
        <CheckboxInput
          id="tts-external-enabled"
          label="Habilitar TTS externo (fallback automatico para edge-tts)"
          checked={external.enabled}
          onChange={(enabled) => patchExternal({ enabled })}
        />

        {external.enabled && (
          <div className="grid gap-4 md:grid-cols-2">
            <Field
              label="Endpoint"
              htmlFor="tts-external-endpoint"
              error={externalEndpointError}
              hint="URL HTTP(S) de sintese"
            >
              <TextInput
                id="tts-external-endpoint"
                type="url"
                value={external.endpoint}
                placeholder="https://api.tts-provider.com/v1/synthesize"
                error={externalEndpointError}
                onChange={(endpoint) => patchExternal({ endpoint })}
              />
            </Field>

            <Field label="API key" htmlFor="tts-external-api-key">
              <TextInput
                id="tts-external-api-key"
                type="password"
                value={external.api_key}
                placeholder="(opcional)"
                onChange={(api_key) => patchExternal({ api_key })}
              />
            </Field>

            <Field label="Formato" htmlFor="tts-external-format">
              <TextInput
                id="tts-external-format"
                value={external.format}
                placeholder="mp3"
                onChange={(format) => patchExternal({ format })}
              />
            </Field>

            <Field
              label="Timeout (s)"
              htmlFor="tts-external-timeout"
              error={externalTimeoutError}
              hint="Numero positivo"
            >
              <NumberInput
                id="tts-external-timeout"
                value={external.timeout}
                min={1}
                step={1}
                error={externalTimeoutError}
                onChange={(timeout) => patchExternal({ timeout })}
              />
            </Field>

            <Field
              label="Velocidade (speed)"
              htmlFor="tts-external-speed"
              error={externalSpeedError}
              hint="0.5 a 2.0"
            >
              <NumberInput
                id="tts-external-speed"
                value={external.params.speed}
                min={0.5}
                max={2.0}
                step={0.1}
                error={externalSpeedError}
                onChange={(speed) =>
                  patchExternal({
                    params: { ...external.params, speed },
                  })
                }
              />
            </Field>
          </div>
        )}
      </div>

      <TestButton label="Testar TTS" state={test} onTest={handleTest} />
    </SectionCard>
  );
}

export default TTSConfig;
