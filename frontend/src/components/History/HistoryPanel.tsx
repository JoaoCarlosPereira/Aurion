// HistoryPanel.tsx — Painel principal de historico de interacoes.
// Consome GET /api/history (limit/offset/search) com busca e paginacao,
// exibe estado de carregamento e de lista vazia, e oferece limpar todo o
// historico via DELETE /api/history (com confirmacao).

import { useCallback, useEffect, useState } from "react";
import { useAurionAPI } from "@/hooks/useAurionAPI";
import type { Interaction } from "@/types";
import { HistorySearch } from "@/components/History/HistorySearch";
import { HistoryItem } from "@/components/History/HistoryItem";

/** Quantidade de itens por pagina. */
const PAGE_SIZE = 20;

/** Painel de historico do Aurion com busca, paginacao e limpeza. */
export function HistoryPanel() {
  const api = useAurionAPI();

  const [items, setItems] = useState<Interaction[]>([]);
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [clearing, setClearing] = useState(false);

  // Carrega uma pagina do historico aplicando o termo de busca atual.
  const loadHistory = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getHistory({
        limit: PAGE_SIZE,
        offset,
        search: search.trim() || undefined,
      });
      setItems(data);
    } catch {
      setError("Falha ao carregar o historico. Tente novamente.");
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [api, offset, search]);

  useEffect(() => {
    void loadHistory();
  }, [loadHistory]);

  // Ao buscar, reinicia para a primeira pagina.
  const handleSearch = useCallback((term: string) => {
    setSearch(term);
    setOffset(0);
  }, []);

  // Limpa todo o historico apos confirmacao do usuario.
  const handleClear = useCallback(async () => {
    const confirmed = window.confirm(
      "Limpar todo o historico? Esta acao nao pode ser desfeita.",
    );
    if (!confirmed) {
      return;
    }
    setClearing(true);
    setError(null);
    try {
      await api.clearHistory();
      setOffset(0);
      setSearch("");
      setItems([]);
      await loadHistory();
    } catch {
      setError("Falha ao limpar o historico. Tente novamente.");
    } finally {
      setClearing(false);
    }
  }, [api, loadHistory]);

  const page = Math.floor(offset / PAGE_SIZE) + 1;
  // Sem total no contrato; assume-se mais paginas quando a pagina vem cheia.
  const hasNextPage = items.length === PAGE_SIZE;
  const hasPrevPage = offset > 0;

  return (
    <section className="flex h-full flex-col gap-4" aria-label="Historico">
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="text-xl font-semibold text-cyan">Historico</h2>
        <button
          type="button"
          onClick={() => void handleClear()}
          disabled={clearing}
          className="ml-auto rounded-lg border border-red-500/40 px-3 py-1.5 text-sm font-semibold text-red-300 transition hover:bg-red-500/10 disabled:opacity-50"
          data-testid="history-clear-button"
        >
          {clearing ? "Limpando..." : "Limpar historico"}
        </button>
      </div>

      <HistorySearch value={search} onSearch={handleSearch} />

      <div className="flex flex-1 flex-col gap-3 rounded-2xl border border-cyan/20 bg-pacman-bg/40 p-4 backdrop-blur">
        {error ? (
          <p className="text-sm text-red-300" role="alert" data-testid="history-error">
            {error}
          </p>
        ) : null}

        {loading ? (
          <p className="text-slate-400" role="status" data-testid="history-loading">
            Carregando historico...
          </p>
        ) : items.length === 0 ? (
          <p className="text-slate-400" data-testid="history-empty">
            Nenhuma interacao encontrada.
          </p>
        ) : (
          <ul className="flex flex-col gap-2" data-testid="history-list">
            {items.map((interaction) => (
              <HistoryItem key={interaction.id} interaction={interaction} />
            ))}
          </ul>
        )}
      </div>

      {/* Controles de paginacao. */}
      <div className="flex items-center justify-between">
        <button
          type="button"
          onClick={() => setOffset((value) => Math.max(0, value - PAGE_SIZE))}
          disabled={!hasPrevPage || loading}
          className="rounded-lg border border-cyan/30 px-3 py-1.5 text-sm font-semibold text-cyan transition hover:bg-cyan/10 disabled:opacity-40"
          data-testid="history-prev-button"
        >
          Anterior
        </button>

        <span className="text-sm text-slate-400" data-testid="history-page">
          Pagina {page}
        </span>

        <button
          type="button"
          onClick={() => setOffset((value) => value + PAGE_SIZE)}
          disabled={!hasNextPage || loading}
          className="rounded-lg border border-cyan/30 px-3 py-1.5 text-sm font-semibold text-cyan transition hover:bg-cyan/10 disabled:opacity-40"
          data-testid="history-next-button"
        >
          Proxima
        </button>
      </div>
    </section>
  );
}

export default HistoryPanel;
