// HistorySearch.test.tsx — Testes unitarios do campo de busca do historico.
// Stack de teste: Vitest + React Testing Library.
// @ts-nocheck — devDependencies de teste ainda nao instaladas; ver task_15.

import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { HistorySearch } from "@/components/History/HistorySearch";

describe("HistorySearch", () => {
  it("renderiza o campo com o valor inicial", () => {
    render(<HistorySearch value="clima" onSearch={() => {}} />);
    expect(screen.getByTestId("history-search-input")).toHaveValue("clima");
  });

  it("dispara onSearch (com debounce) ao digitar", async () => {
    const onSearch = vi.fn();
    render(<HistorySearch value="" onSearch={onSearch} debounceMs={10} />);
    fireEvent.change(screen.getByTestId("history-search-input"), {
      target: { value: "agenda" },
    });
    await waitFor(() => expect(onSearch).toHaveBeenCalledWith("agenda"));
  });

  it("nao dispara onSearch quando o termo nao muda", () => {
    const onSearch = vi.fn();
    render(<HistorySearch value="x" onSearch={onSearch} debounceMs={10} />);
    expect(onSearch).not.toHaveBeenCalled();
  });
});
