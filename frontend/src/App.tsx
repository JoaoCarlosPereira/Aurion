// App.tsx — Layout raiz e rotas da SPA (Chat, Historico, Configuracoes).
// As rotas importam componentes PLACEHOLDER; as tasks 13-17 preenchem cada area
// sem precisar editar este arquivo de roteamento compartilhado.

import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { ChatPanel } from "@/components/Chat/ChatPanel";
import { HistoryPanel } from "@/components/History/HistoryPanel";
import { SettingsPanel } from "@/components/Settings/SettingsPanel";

/** Item de navegacao com estilo ativo. */
function NavItem({ to, label }: { to: string; label: string }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        [
          "rounded-lg px-4 py-2 text-sm font-semibold transition",
          isActive
            ? "bg-cyan/20 text-cyan"
            : "text-slate-300 hover:text-cyan",
        ].join(" ")
      }
    >
      {label}
    </NavLink>
  );
}

/** Componente raiz: cabecalho de navegacao + area de conteudo roteada. */
export function App() {
  return (
    <div className="flex min-h-screen flex-col bg-pacman-bg text-slate-100">
      <header className="border-b border-cyan/20 px-6 py-4">
        <div className="mx-auto flex max-w-5xl items-center gap-6">
          <span className="text-lg font-extrabold text-cyan">Aurion</span>
          <nav className="flex items-center gap-2">
            <NavItem to="/chat" label="Chat" />
            <NavItem to="/historico" label="Historico" />
            <NavItem to="/config" label="Configuracoes" />
          </nav>
        </div>
      </header>

      <main className="mx-auto w-full max-w-5xl flex-1 p-6">
        <Routes>
          <Route path="/" element={<Navigate to="/chat" replace />} />
          <Route path="/chat" element={<ChatPanel />} />
          <Route path="/historico" element={<HistoryPanel />} />
          <Route path="/config" element={<SettingsPanel />} />
          <Route path="*" element={<Navigate to="/chat" replace />} />
        </Routes>
      </main>
    </div>
  );
}

export default App;
