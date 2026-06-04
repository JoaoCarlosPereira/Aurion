// SettingsPanel.tsx — Painel completo de configuracoes.
// Compoem todos os sub-paineis (Hermes, STT, TTS, Audio, WakeWord) em um
// unico formulario com validacao, botoes de teste e salvamento.

import { useCallback, useEffect, useMemo, useState } from "react";
import type { AppConfig } from "@/types";
import { useAurionAPI } from "@/hooks/useAurionAPI";
import { HermesConfig } from "./HermesConfig";
import { STTConfig } from "./STTConfig";
import { TTSConfig } from "./TTSConfig";
import { AudioConfig } from "./AudioConfig";
import { WakeWordConfig } from "./WakeWordConfig";

/** Estado de feedback do botao de salvar. */
type SaveStatus = "idle" | "saving" | "saved" | "error";

/** Valores padrao da configuracao (espelham AppConfig do backend). */
const DEFAULT_CONFIG: AppConfig = {
  hermes: { endpoint: "http://localhost:8080", auth_token: "" },
  stt: {
    engine: "whisper.cpp",
    model: "ggml-base-q4",
    language: "pt-BR",
    threads: 2,
    beam_size: 1,
    max_context: -1,
  },
  tts: {
    engine: "edge-tts",
    voice: "pt-BR-FabioNeural",
    rate: 0,
    volume: 100,
    external: {
      enabled: false,
      endpoint: "https://api.tts-provider.com/v1/synthesize",
      api_key: "",
      params: { input: "", voice: "", speed: 1.0 },
      format: "mp3",
      timeout: 10,
    },
  },
  wake_word: { engine: "porcupine", sensitivity: 0.5, keyword: "aurion" },
  audio: {
    sample_rate: 16000,
    channels: 1,
    chunk_size: 1024,
    silence_threshold: 300,
    wake_word_timeout: 10,
  },
};

/** Painel de configuracoes do Aurion. */
export function SettingsPanel() {
  const apiClient = useAurionAPI();
  const [config, setConfig] = useState<AppConfig>(DEFAULT_CONFIG);
  const [loading, setLoading] = useState(true);
  const [saveStatus, setSaveStatus] = useState<SaveStatus>("idle");
  const [sectionValidities, setSectionValidities] = useState<Record<string, boolean>>({});

  // Carregar configuracoes do backend ao montar.
  useEffect(() => {
    let mounted = true;
    setLoading(true);

    apiClient
      .getConfig()
      .then((cfg: AppConfig) => {
        if (mounted) {
          setConfig(cfg as unknown as AppConfig);
        }
      })
      .catch(() => {
        // Backend indisponivel (dev): usa valores padrao.
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });

    return () => {
      mounted = false;
    };
  }, []);

  // Verificar se todas as secoes estao validas.
  const allValid = useMemo(() => {
    return Object.values(sectionValidities).every(Boolean);
  }, [sectionValidities]);

  // Handler de alteracao por secao.
  const handleChange = useCallback(
    (section: keyof AppConfig, value: unknown) => {
      setConfig((prev) => ({ ...prev, [section]: value }));
    },
    [],
  );

  // Registro de validade por secao.
  const handleValidityChange = useCallback((section: string, valid: boolean) => {
    setSectionValidities((prev) => ({ ...prev, [section]: valid }));
  }, []);

  // Salvar configuracoes.
  const handleSave = useCallback(async () => {
    setSaveStatus("saving");
    try {
      await apiClient.updateConfig(config);
      setSaveStatus("saved");
      setTimeout(() => setSaveStatus("idle"), 2000);
    } catch {
      setSaveStatus("error");
      setTimeout(() => setSaveStatus("idle"), 3000);
    }
  }, [config]);

  // Reset para padroes.
  const handleReset = useCallback(async () => {
    try {
      await apiClient.updateConfig(DEFAULT_CONFIG);
      setConfig(DEFAULT_CONFIG);
      setSectionValidities({});
    } catch {
      // ignora erro em dev (backend indisponivel).
    }
  }, []);

  if (loading) {
    return (
      <section className="flex h-full flex-col items-center justify-center gap-3" aria-label="Carregando configuracoes">
        <span className="text-lg font-semibold text-cyan">Carregando configuracoes...</span>
      </section>
    );
  }

  return (
    <section className="flex h-full flex-col gap-4" aria-label="Configuracoes">
      {/* Cabecalho com acoes globais */}
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-cyan">Configuracoes</h2>
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={handleReset}
            className="rounded-lg border border-slate-500/40 bg-slate-700/40 px-3 py-2 text-sm text-slate-300 transition hover:bg-slate-600/40"
          >
            Restaurar padroes
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={!allValid || saveStatus === "saving"}
            className={`rounded-lg border px-4 py-2 text-sm font-semibold transition ${
              saveStatus === "saved"
                ? "border-[#22c55e]/60 bg-[#22c55e]/20 text-[#22c55e]"
                : saveStatus === "error"
                  ? "border-[#ef4444]/60 bg-[#ef4444]/20 text-[#ef4444]"
                  : "border-cyan/40 bg-cyan/20 text-cyan hover:bg-cyan/30 disabled:cursor-not-allowed disabled:opacity-50"
            }`}
          >
            {saveStatus === "saving"
              ? "Salvando..."
              : saveStatus === "saved"
                ? "Salvo!"
                : saveStatus === "error"
                  ? "Erro ao salvar"
                  : "Salvar"}
          </button>
        </div>
      </div>

      {/* Mensagem de feedback global */}
      {saveStatus === "saved" && (
        <div className="rounded-lg border border-[#22c55e]/30 bg-[#22c55e]/10 p-3 text-sm text-[#22c55e]">
          Configuracoes salvas com sucesso.
        </div>
      )}
      {saveStatus === "error" && (
        <div className="rounded-lg border border-[#ef4444]/30 bg-[#ef4444]/10 p-3 text-sm text-[#ef4444]">
          Erro ao salvar as configuracoes. Verifique o backend.
        </div>
      )}

      {/* Sub-paineis */}
      <div className="flex-1 space-y-4 overflow-y-auto">
        <HermesConfig
          value={config.hermes}
          onChange={(v) => handleChange("hermes", v)}
          onValidityChange={(valid) => handleValidityChange("hermes", valid)}
        />

        <STTConfig
          value={config.stt}
          onChange={(v) => handleChange("stt", v)}
          onValidityChange={(valid) => handleValidityChange("stt", valid)}
        />

        <TTSConfig
          value={config.tts}
          onChange={(v) => handleChange("tts", v)}
          onValidityChange={(valid) => handleValidityChange("tts", valid)}
        />

        <WakeWordConfig
          value={config.wake_word}
          onChange={(v) => handleChange("wake_word", v)}
          onValidityChange={(valid) => handleValidityChange("wakeword", valid)}
        />

        <AudioConfig
          value={config.audio}
          onChange={(v) => handleChange("audio", v)}
          onValidityChange={(valid) => handleValidityChange("audio", valid)}
        />
      </div>
    </section>
  );
}

export default SettingsPanel;
