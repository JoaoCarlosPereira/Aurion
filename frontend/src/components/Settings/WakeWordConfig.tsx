// WakeWordConfig.tsx — Sub-painel de configuracao da deteccao de wake word.
// Edita engine, sensitivity (0.0-1.0) e keyword (TechSpec 4.2 / 5.2), validando a faixa
// de sensibilidade. Nao possui botao de teste proprio (sem endpoint dedicado na TechSpec 3.1).

import { useEffect } from "react";
import type { WakeWordConfig as WakeWordConfigType } from "@/types";
import {
  Field,
  NumberInput,
  SectionCard,
  TextInput,
  validateNumberRange,
} from "@/components/Settings/settingsShared";

/** Props do sub-painel de wake word. */
export interface WakeWordConfigProps {
  value: WakeWordConfigType;
  onChange: (value: WakeWordConfigType) => void;
  onValidityChange?: (valid: boolean) => void;
}

/** Formulario de configuracao do wake word ("Aurion"). */
export function WakeWordConfig({
  value,
  onChange,
  onValidityChange,
}: WakeWordConfigProps) {
  // Validacao da sensibilidade (0.0 a 1.0, TechSpec 5.2).
  const sensitivityError = validateNumberRange(value.sensitivity, 0, 1);
  const keywordError =
    value.keyword.trim().length === 0 ? "Palavra-chave obrigatoria." : null;
  const valid = sensitivityError === null && keywordError === null;

  useEffect(() => {
    onValidityChange?.(valid);
  }, [valid, onValidityChange]);

  return (
    <SectionCard
      title="Wake Word"
      description='Deteccao continua da palavra de ativacao ("Aurion").'
    >
      <div className="grid gap-4 md:grid-cols-2">
        <Field label="Engine" htmlFor="wakeword-engine">
          <TextInput
            id="wakeword-engine"
            value={value.engine}
            placeholder="porcupine"
            onChange={(engine) => onChange({ ...value, engine })}
          />
        </Field>

        <Field label="Palavra-chave" htmlFor="wakeword-keyword" error={keywordError}>
          <TextInput
            id="wakeword-keyword"
            value={value.keyword}
            placeholder="aurion"
            error={keywordError}
            onChange={(keyword) => onChange({ ...value, keyword })}
          />
        </Field>

        <Field
          label="Sensibilidade"
          htmlFor="wakeword-sensitivity"
          error={sensitivityError}
          hint="0.0 a 1.0 (padrao 0.5)"
        >
          <NumberInput
            id="wakeword-sensitivity"
            value={value.sensitivity}
            min={0}
            max={1}
            step={0.05}
            error={sensitivityError}
            onChange={(sensitivity) => onChange({ ...value, sensitivity })}
          />
        </Field>
      </div>
    </SectionCard>
  );
}

export default WakeWordConfig;
