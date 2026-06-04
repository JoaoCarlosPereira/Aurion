// ChatInput.tsx — Campo de entrada de comando por texto do chat.
// Permite digitar e enviar comandos; Enter envia, Shift+Enter quebra linha.
// O envio efetivo (POST /api/command) e responsabilidade do ChatPanel via callback.

import { useState, type KeyboardEvent } from "react";

export interface ChatInputProps {
  /** Callback disparado ao enviar um comando nao vazio. */
  onSend: (message: string) => void;
  /** Desabilita o input enquanto um comando esta sendo processado. */
  disabled?: boolean;
  /** Placeholder do campo (padrao: "Digite um comando..."). */
  placeholder?: string;
}

/**
 * Input de texto com botao de envio para comandos do chat.
 *
 * Mantem o texto em estado local controlado e delega o envio ao componente pai.
 */
export function ChatInput({
  onSend,
  disabled = false,
  placeholder = "Digite um comando...",
}: ChatInputProps) {
  const [value, setValue] = useState("");

  const canSend = value.trim().length > 0 && !disabled;

  /** Valida e dispara o envio, limpando o campo em seguida. */
  function submit() {
    const text = value.trim();
    if (!text || disabled) {
      return;
    }
    onSend(text);
    setValue("");
  }

  /** Enter envia; Shift+Enter insere quebra de linha. */
  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  }

  return (
    <form
      className="flex flex-1 items-end gap-3"
      aria-label="Enviar comando"
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
      <textarea
        value={value}
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        rows={1}
        placeholder={placeholder}
        aria-label="Comando"
        className="max-h-40 min-h-[3rem] flex-1 resize-none rounded-xl border border-cyan/20 bg-pacman-bg/40 px-4 py-3 text-sm text-slate-100 placeholder:text-slate-500 backdrop-blur outline-none transition focus:border-cyan/60 disabled:opacity-50"
      />
      <button
        type="submit"
        disabled={!canSend}
        aria-label="Enviar"
        className="flex h-12 items-center justify-center rounded-xl border-2 border-cyan bg-cyan/10 px-5 text-sm font-semibold text-cyan transition hover:bg-cyan/20 disabled:cursor-not-allowed disabled:opacity-40"
      >
        Enviar
      </button>
    </form>
  );
}

export default ChatInput;
