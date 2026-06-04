// HistoryPanel.test.tsx — Testes unitarios do painel de historico.
// Stack de teste: Vitest + React Testing Library.
// Mocka o hook useAurionAPI para simular as chamadas REST do backend.
// @ts-nocheck — devDependencies de teste ainda nao instaladas; ver task_15.

import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { HistoryPanel } from "@/components/History/HistoryPanel";
import type { Interaction } from "@/types";

// --- Mock do hook de API ---
const getHistory = vi.fn();
const clearHistory = vi.fn();

vi.mock("@/hooks/useAurionAPI", () => ({
  useAurionAPI: () => ({ getHistory, clearHistory }),
}));

/** Gera uma lista de interacoes de teste. */
function makeInteractions(count: number): Interaction[] {
  return Array.from({ length: count }, (_, index) => ({
    id: String(index + 1),
    timestamp: "2026-06-04T12:00:00.000Z",
    channel: index % 2 === 0 ? "local" : "web",
    input_text: `comando ${index + 1}`,
    output_text: `resposta ${index + 1}`,
    output_audio_url: null,
    duration_ms: 100,
    status: "success",
    error_message: null,
  }));
}

describe("HistoryPanel", () => {
  beforeEach(() => {
    getHistory.mockReset();
    clearHistory.mockReset();
  });

  it("exibe indicador de carregamento e depois a lista", async () => {
    getHistory.mockResolvedValueOnce(makeInteractions(2));
    render(<HistoryPanel />);
    // O estado de loading aparece sincronicamente no primeiro render.
    expect(screen.getByTestId("history-loading")).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByTestId("history-list")).toBeInTheDocument(),
    );
  });

  it("exibe mensagem de lista vazia quando nao ha interacoes", async () => {
    getHistory.mockResolvedValueOnce([]);
    render(<HistoryPanel />);
    await waitFor(() =>
      expect(screen.getByTestId("history-empty")).toBeInTheDocument(),
    );
  });

  it("busca por texto chamando getHistory com search", async () => {
    getHistory.mockResolvedValue([]);
    render(<HistoryPanel />);
    await waitFor(() => expect(getHistory).toHaveBeenCalled());
    fireEvent.change(screen.getByTestId("history-search-input"), {
      target: { value: "agenda" },
    });
    await waitFor(() =>
      expect(getHistory).toHaveBeenLastCalledWith(
        expect.objectContaining({ search: "agenda", offset: 0 }),
      ),
    );
  });

  it("pagina avancando o offset com limit", async () => {
    // Primeira pagina cheia (20) habilita o botao "Proxima".
    getHistory.mockResolvedValue(makeInteractions(20));
    render(<HistoryPanel />);
    await waitFor(() =>
      expect(screen.getByTestId("history-list")).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByTestId("history-next-button"));
    await waitFor(() =>
      expect(getHistory).toHaveBeenLastCalledWith(
        expect.objectContaining({ limit: 20, offset: 20 }),
      ),
    );
  });

  it("limpa o historico apos confirmacao", async () => {
    getHistory.mockResolvedValue(makeInteractions(1));
    clearHistory.mockResolvedValueOnce(undefined);
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
    render(<HistoryPanel />);
    await waitFor(() =>
      expect(screen.getByTestId("history-list")).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByTestId("history-clear-button"));
    await waitFor(() => expect(clearHistory).toHaveBeenCalled());
    confirmSpy.mockRestore();
  });

  it("nao limpa o historico quando o usuario cancela a confirmacao", async () => {
    getHistory.mockResolvedValue(makeInteractions(1));
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(false);
    render(<HistoryPanel />);
    await waitFor(() =>
      expect(screen.getByTestId("history-list")).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByTestId("history-clear-button"));
    expect(clearHistory).not.toHaveBeenCalled();
    confirmSpy.mockRestore();
  });
});
