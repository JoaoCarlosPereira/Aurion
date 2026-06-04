// useAurionAPI.ts — Hook de acesso a API REST do Aurion.
// Expoe o wrapper axios estavel para os componentes consumirem.

import { useMemo } from "react";
import { api, type AurionAPI } from "@/services/api";

/**
 * Retorna o conjunto de operacoes da API REST do Aurion.
 * O objeto e estavel entre renderizacoes (memoizado).
 */
export function useAurionAPI(): AurionAPI {
  return useMemo(() => api, []);
}
