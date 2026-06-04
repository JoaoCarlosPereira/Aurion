// HistorySearch.tsx — Campo de busca textual do historico.
// Controlado pelo HistoryPanel; aplica debounce para evitar requisicoes
// excessivas ao endpoint GET /api/history?search=.

import { useEffect, useState } from "react";

/** Props do campo de busca de historico. */
export interface HistorySearchProps {
  /** Valor inicial do termo de busca. */
  value: string;
  /** Disparado (com debounce) quando o termo de busca muda. */
  onSearch: (term: string) => void;
  /** Atraso do debounce em ms (padrao 300). */
  debounceMs?: number;
}

/** Campo de busca com debounce para filtrar o historico por texto. */
export function HistorySearch({
  value,
  onSearch,
  debounceMs = 300,
}: HistorySearchProps) {
  const [term, setTerm] = useState(value);

  // Mantem o estado local sincronizado quando o valor externo muda.
  useEffect(() => {
    setTerm(value);
  }, [value]);

  // Aplica debounce: so notifica o pai apos o usuario parar de digitar.
  useEffect(() => {
    if (term === value) {
      return;
    }
    const handle = window.setTimeout(() => onSearch(term), debounceMs);
    return () => window.clearTimeout(handle);
  }, [term, value, debounceMs, onSearch]);

  return (
    <div className="relative">
      <input
        type="search"
        value={term}
        onChange={(event) => setTerm(event.target.value)}
        placeholder="Buscar no historico..."
        aria-label="Buscar no historico"
        className="w-full rounded-xl border border-cyan/20 bg-pacman-bg/40 px-4 py-2 text-sm text-slate-100 outline-none backdrop-blur placeholder:text-slate-500 focus:border-cyan"
        data-testid="history-search-input"
      />
    </div>
  );
}

export default HistorySearch;
