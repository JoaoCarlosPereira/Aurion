// HermesConfig.tsx — Sub-painel de configuracao do Hermes Agent.
// Edita endpoint e auth_token, valida a URL e testa a conexao via POST /api/test/hermes.

import { useEffect, useState } from "react";
import type { HermesConfig as HermesConfigType } from "@/types";
import { useAurionAPI } from "@/hooks/useAurionAPI";
import {
  Field,
  SectionCard,
  TestButton,
  TextInput,
  initialTestState,
  validateUrl,
  type InlineTestState,
} from "@/components/Settings/settingsShared";

/** Props comuns a todos os sub-paineis: valor, alteracao e reporte de validade. */
export interface HermesConfigProps {
  value: HermesConfigType;
  onChange: (value: HermesConfigType) => void;
  /** Reporta se a secao esta valida (usado para habilitar o salvar). */
  onValidityChange?: (valid: boolean) => void;
}

/** Formulario de configuracao do Hermes Agent. */
export function HermesConfig({
  value,
  onChange,
  onValidityChange,
}: HermesConfigProps) {
  const apiClient = useAurionAPI();
  const [test, setTest] = useState<InlineTestState>(initialTestState);

  // Validacao do endpoint (URL obrigatoria).
  const endpointError = validateUrl(value.endpoint, true);
  const valid = endpointError === null;

  useEffect(() => {
    onValidityChange?.(valid);
  }, [valid, onValidityChange]);

  /** Dispara o teste de conexao e exibe o resultado inline. */
  async function handleTest() {
    setTest({ status: "loading", message: null });
    try {
      const result = await apiClient.testHermes();
      setTest({
        status: result.ok ? "success" : "error",
        message: result.message,
      });
    } catch {
      setTest({
        status: "error",
        message: "Falha ao testar a conexao com o Hermes.",
      });
    }
  }

  return (
    <SectionCard
      title="Hermes Agent"
      description="Conexao HTTP REST com o agente que processa os comandos."
    >
      <Field
        label="Endpoint"
        htmlFor="hermes-endpoint"
        error={endpointError}
        hint="Ex: http://localhost:8080"
      >
        <TextInput
          id="hermes-endpoint"
          type="url"
          value={value.endpoint}
          placeholder="http://localhost:8080"
          error={endpointError}
          onChange={(endpoint) => onChange({ ...value, endpoint })}
        />
      </Field>

      <Field label="Token de autenticacao" htmlFor="hermes-token">
        <TextInput
          id="hermes-token"
          type="password"
          value={value.auth_token}
          placeholder="(opcional)"
          onChange={(auth_token) => onChange({ ...value, auth_token })}
        />
      </Field>

      <TestButton label="Testar Hermes" state={test} onTest={handleTest} />
    </SectionCard>
  );
}

export default HermesConfig;
