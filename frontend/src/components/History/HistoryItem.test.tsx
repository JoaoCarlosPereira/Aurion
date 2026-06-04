// HistoryItem.test.tsx — Testes unitarios do item de historico.
// Stack de teste: Vitest + React Testing Library (adicionar como devDependencies
// junto com jsdom e @testing-library/jest-dom; ver notas da task_15).
// @ts-nocheck — as devDependencies de teste ainda nao estao instaladas no
// ambiente; o @ts-nocheck mantem `tsc --noEmit` verde sem editar o tsconfig
// compartilhado. Remover apos instalar vitest/@testing-library.

import { describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { HistoryItem } from "@/components/History/HistoryItem";
import type { Interaction } from "@/types";

/** Cria uma interacao de teste com sobrescritas opcionais. */
function makeInteraction(overrides: Partial<Interaction> = {}): Interaction {
  return {
    id: "1",
    timestamp: "2026-06-04T12:00:00.000Z",
    channel: "local",
    input_text: "Qual o clima hoje?",
    output_text: "Esta ensolarado.",
    output_audio_url: null,
    duration_ms: 1200,
    status: "success",
    ...overrides,
  } as Interaction;
}

describe("HistoryItem", () => {
  it("renderiza dados validos (entrada, status e timestamp)", () => {
    render(<HistoryItem interaction={makeInteraction()} />);
    expect(screen.getByText("Qual o clima hoje?")).toBeInTheDocument();
    expect(screen.getByTestId("history-status")).toHaveTextContent("Sucesso");
    expect(screen.getByTestId("history-timestamp")).toBeInTheDocument();
  });

  it("exibe indicador visual de canal local", () => {
    render(<HistoryItem interaction={makeInteraction({ channel: "local" })} />);
    expect(screen.getByTestId("history-channel")).toHaveTextContent("Local");
  });

  it("exibe indicador visual de canal web", () => {
    render(<HistoryItem interaction={makeInteraction({ channel: "web" })} />);
    expect(screen.getByTestId("history-channel")).toHaveTextContent("Web");
  });

  it("exibe status de erro com mensagem ao expandir", () => {
    render(
      <HistoryItem
        interaction={makeInteraction({
          status: "error",
          error_message: "Hermes indisponivel",
        })}
      />,
    );
    expect(screen.getByTestId("history-status")).toHaveTextContent("Erro");
    fireEvent.click(screen.getByRole("button"));
    expect(screen.getByText("Hermes indisponivel")).toBeInTheDocument();
  });

  it("exibe status de timeout", () => {
    render(<HistoryItem interaction={makeInteraction({ status: "timeout" })} />);
    expect(screen.getByTestId("history-status")).toHaveTextContent(
      "Tempo esgotado",
    );
  });

  it("alterna expand/collapse ao clicar", () => {
    render(<HistoryItem interaction={makeInteraction()} />);
    const toggle = screen.getByRole("button");
    expect(screen.queryByTestId("history-details")).not.toBeInTheDocument();
    fireEvent.click(toggle);
    expect(screen.getByTestId("history-details")).toBeInTheDocument();
    fireEvent.click(toggle);
    expect(screen.queryByTestId("history-details")).not.toBeInTheDocument();
  });

  it("formata o timestamp em pt-BR", () => {
    render(<HistoryItem interaction={makeInteraction()} />);
    const time = screen.getByTestId("history-timestamp");
    // O texto deve diferir do ISO bruto apos a formatacao.
    expect(time.textContent).not.toEqual("2026-06-04T12:00:00.000Z");
  });
});
