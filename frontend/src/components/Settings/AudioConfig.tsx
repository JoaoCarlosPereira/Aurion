// AudioConfig.tsx — Sub-painel de configuracao de captura de audio (PyAudio).
// Edita sample_rate, channels, chunk_size, silence_threshold e wake_word_timeout
// (TechSpec 4.2 / 5.1), validando os campos numericos. Nao possui botao de teste
// proprio (nao ha endpoint POST /api/test/audio na TechSpec 3.1).

import { useEffect } from "react";
import type { AudioConfig as AudioConfigType } from "@/types";
import {
  Field,
  NumberInput,
  SectionCard,
  SelectInput,
  validateNumberRange,
  validatePositive,
} from "@/components/Settings/settingsShared";

/** Props do sub-painel de audio. */
export interface AudioConfigProps {
  value: AudioConfigType;
  onChange: (value: AudioConfigType) => void;
  onValidityChange?: (valid: boolean) => void;
}

/** Numero de canais suportados (mono recomendado para STT). */
const CHANNEL_OPTIONS = [
  { value: "1", label: "1 (mono)" },
  { value: "2", label: "2 (estereo)" },
] as const;

/** Formulario de configuracao de audio. */
export function AudioConfig({
  value,
  onChange,
  onValidityChange,
}: AudioConfigProps) {
  // Validacao dos campos numericos.
  const sampleRateError = validatePositive(value.sample_rate, {
    integer: true,
  });
  const chunkSizeError = validatePositive(value.chunk_size, { integer: true });
  const silenceError = validatePositive(value.silence_threshold, {
    integer: true,
  });
  const timeoutError = validateNumberRange(value.wake_word_timeout, 1, 120, {
    integer: true,
  });
  const valid =
    sampleRateError === null &&
    chunkSizeError === null &&
    silenceError === null &&
    timeoutError === null;

  useEffect(() => {
    onValidityChange?.(valid);
  }, [valid, onValidityChange]);

  return (
    <SectionCard
      title="Audio"
      description="Parametros de captura do microfone local (PyAudio)."
    >
      <div className="grid gap-4 md:grid-cols-2">
        <Field
          label="Sample rate (Hz)"
          htmlFor="audio-sample-rate"
          error={sampleRateError}
          hint="Ex: 16000"
        >
          <NumberInput
            id="audio-sample-rate"
            value={value.sample_rate}
            min={1}
            step={1000}
            error={sampleRateError}
            onChange={(sample_rate) => onChange({ ...value, sample_rate })}
          />
        </Field>

        <Field label="Canais" htmlFor="audio-channels">
          <SelectInput
            id="audio-channels"
            value={String(value.channels)}
            options={CHANNEL_OPTIONS}
            onChange={(channels) =>
              onChange({ ...value, channels: Number(channels) })
            }
          />
        </Field>

        <Field
          label="Chunk size"
          htmlFor="audio-chunk-size"
          error={chunkSizeError}
          hint="Ex: 1024"
        >
          <NumberInput
            id="audio-chunk-size"
            value={value.chunk_size}
            min={1}
            step={256}
            error={chunkSizeError}
            onChange={(chunk_size) => onChange({ ...value, chunk_size })}
          />
        </Field>

        <Field
          label="Limiar de silencio"
          htmlFor="audio-silence-threshold"
          error={silenceError}
          hint="Ex: 300"
        >
          <NumberInput
            id="audio-silence-threshold"
            value={value.silence_threshold}
            min={1}
            step={50}
            error={silenceError}
            onChange={(silence_threshold) =>
              onChange({ ...value, silence_threshold })
            }
          />
        </Field>

        <Field
          label="Timeout do wake word (s)"
          htmlFor="audio-wake-word-timeout"
          error={timeoutError}
          hint="1 a 120"
        >
          <NumberInput
            id="audio-wake-word-timeout"
            value={value.wake_word_timeout}
            min={1}
            max={120}
            step={1}
            error={timeoutError}
            onChange={(wake_word_timeout) =>
              onChange({ ...value, wake_word_timeout })
            }
          />
        </Field>
      </div>
    </SectionCard>
  );
}

export default AudioConfig;
