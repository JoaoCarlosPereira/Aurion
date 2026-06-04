// main.tsx — Entry point da SPA: monta o React no #root com o roteador.

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { App } from "@/App";
import "@/styles/main.css";

const container = document.getElementById("root");
if (!container) {
  throw new Error("Elemento #root nao encontrado no index.html");
}

createRoot(container).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>,
);
