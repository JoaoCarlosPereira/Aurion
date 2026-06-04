// settingsShared.tsx — Primitivos de UI e helpers de validacao compartilhados
// pelos sub-paineis de configuracao (Hermes, STT, TTS, Audio, Wake Word).
// Identificadores em ingles; comentarios em PT-BR conforme convencao do projeto.

import type { ChangeEvent, ReactNode } from "react";

// ---------------------------------------------------------------------------
// Validacao
// ---------------------------------------------------------------------------

/** Mensagem de erro de validacao, ou null quando o valor e valido. */
export type ValidationError = string | null;

/**
 * Valida uma URL HTTP(S). Aceita string vazia quando `required` e false.
 */
export function validateUrl(value: string, required = true): ValidationError {
  const trimmed = value.trim();
  if (!trimmed) {
    return required ? "Endereco obrigatorio." : null;
  }
  try {
    const url = new URL(trimmed);
    if (url.protocol !== "http:" && url.protocol !== "https:") {
      return "Use um endereco http:// ou https://.";
    }
    return null;
  } catch {
    return "URL invalida.";
  }
}

/**
 * Valida um numero dentro de uma faixa fechada [min, max].
 * `integer` exige valor inteiro; util para sample_rate, threads etc.
 */
export function validateNumberRange(
  value: number,
  min: number,
  max: number,
  options: { integer?: boolean } = {},
): ValidationError {
  if (Number.isNaN(value)) {
    return "Informe um numero valido.";
  }
  if (options.integer && !Number.isInteger(value)) {
    return "Informe um numero inteiro.";
  }
  if (value < min || value > max) {
    return `Valor deve estar entre ${min} e ${max}.`;
  }
  return null;
}

/** Valida um numero estritamente positivo (ex: sample_rate, chunk_size). */
export function validatePositive(
  value: number,
  options: { integer?: boolean } = {},
): ValidationError {
  if (Number.isNaN(value)) {
    return "Informe um numero valido.";
  }
  if (options.integer && !Number.isInteger(value)) {
    return "Informe um numero inteiro.";
  }
  if (value <= 0) {
    return "Valor deve ser positivo.";
  }
  return null;
}

// ---------------------------------------------------------------------------
// Primitivos de formulario
// ---------------------------------------------------------------------------

/** Rotulo + controle + mensagem de erro, com estilizacao do tema Pac-Man. */
export function Field({
  label,
  htmlFor,
  error,
  hint,
  children,
}: {
  label: string;
  htmlFor: string;
  error?: ValidationError;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1">
      <label
        htmlFor={htmlFor}
        className="text-xs font-semibold uppercase tracking-wide text-slate-300"
      >
        {label}
      </label>
      {children}
      {hint && !error && <span className="text-xs text-slate-500">{hint}</span>}
      {error && (
        <span role="alert" className="text-xs text-[#ef4444]">
          {error}
        </span>
      )}
    </div>
  );
}

const inputBaseClass =
  "rounded-lg border bg-pacman-bg/60 px-3 py-2 text-sm text-slate-100 " +
  "outline-none transition focus:border-cyan focus:ring-1 focus:ring-cyan/40";

/** Calcula a classe de borda conforme presenca de erro. */
function borderClass(error?: ValidationError): string {
  return error ? "border-[#ef4444]/70" : "border-cyan/20";
}

/** Campo de texto generico (texto, senha, URL). */
export function TextInput({
  id,
  value,
  onChange,
  type = "text",
  placeholder,
  error,
}: {
  id: string;
  value: string;
  onChange: (value: string) => void;
  type?: "text" | "password" | "url";
  placeholder?: string;
  error?: ValidationError;
}) {
  return (
    <input
      id={id}
      type={type}
      value={value}
      placeholder={placeholder}
      aria-invalid={Boolean(error)}
      onChange={(e: ChangeEvent<HTMLInputElement>) => onChange(e.target.value)}
      className={`${inputBaseClass} ${borderClass(error)}`}
    />
  );
}

/** Campo numerico que entrega o valor ja convertido para number. */
export function NumberInput({
  id,
  value,
  onChange,
  step,
  min,
  max,
  error,
}: {
  id: string;
  value: number;
  onChange: (value: number) => void;
  step?: number;
  min?: number;
  max?: number;
  error?: ValidationError;
}) {
  return (
    <input
      id={id}
      type="number"
      value={Number.isNaN(value) ? "" : value}
      step={step}
      min={min}
      max={max}
      aria-invalid={Boolean(error)}
      onChange={(e: ChangeEvent<HTMLInputElement>) =>
        onChange(e.target.valueAsNumber)
      }
      className={`${inputBaseClass} ${borderClass(error)}`}
    />
  );
}

/** Campo de selecao (dropdown) com opcoes. */
export function SelectInput({
  id,
  value,
  onChange,
  options,
  error,
}: {
  id: string;
  value: string;
  onChange: (value: string) => void;
  options: ReadonlyArray<{ value: string; label: string }>;
  error?: ValidationError;
}) {
  return (
    <select
      id={id}
      value={value}
      aria-invalid={Boolean(error)}
      onChange={(e: ChangeEvent<HTMLSelectElement>) => onChange(e.target.value)}
      className={`${inputBaseClass} ${borderClass(error)}`}
    >
      {options.map((opt) => (
        <option key={opt.value} value={opt.value}>
          {opt.label}
        </option>
      ))}
    </select>
  );
}

/** Caixa de selecao booleana (toggle simples). */
export function CheckboxInput({
  id,
  label,
  checked,
  onChange,
}: {
  id: string;
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <label htmlFor={id} className="flex items-center gap-2 text-sm text-slate-200">
      <input
        id={id}
        type="checkbox"
        checked={checked}
        onChange={(e: ChangeEvent<HTMLInputElement>) =>
          onChange(e.target.checked)
        }
        className="h-4 w-4 accent-[#34d3ff]"
      />
      {label}
    </label>
  );
}

// ---------------------------------------------------------------------------
// Botao de teste com estado de resultado
// ---------------------------------------------------------------------------

/** Resultado de um teste de conexao exibido inline (sucesso/erro). */
export interface InlineTestState {
  status: "idle" | "loading" | "success" | "error";
  message: string | null;
}

/** Estado inicial de um teste de conexao. */
export const initialTestState: InlineTestState = {
  status: "idle",
  message: null,
};

/**
 * Botao de teste de conexao que dispara `onTest` e exibe feedback inline.
 * Mantem o estado de loading desabilitado para evitar disparos concorrentes.
 */
export function TestButton({
  label,
  state,
  onTest,
}: {
  label: string;
  state: InlineTestState;
  onTest: () => void;
}) {
  const isLoading = state.status === "loading";
  return (
    <div className="flex items-center gap-3">
      <button
        type="button"
        onClick={onTest}
        disabled={isLoading}
        className="rounded-lg border border-pacman-yellow/60 bg-pacman-yellow/10 px-3 py-2 text-sm font-semibold text-pacman-yellow transition hover:bg-pacman-yellow/20 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {isLoading ? "Testando..." : label}
      </button>
      {state.status === "success" && state.message && (
        <span role="status" className="text-xs text-[#22c55e]">
          {state.message}
        </span>
      )}
      {state.status === "error" && state.message && (
        <span role="alert" className="text-xs text-[#ef4444]">
          {state.message}
        </span>
      )}
    </div>
  );
}

/** Cartao de secao que agrupa um sub-painel de configuracao. */
export function SectionCard({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: ReactNode;
}) {
  return (
    <section className="flex flex-col gap-4 rounded-2xl border border-cyan/20 bg-pacman-bg/40 p-4 backdrop-blur">
      <header className="flex flex-col gap-1">
        <h3 className="text-base font-semibold text-cyan">{title}</h3>
        {description && (
          <p className="text-xs text-slate-400">{description}</p>
        )}
      </header>
      {children}
    </section>
  );
}
