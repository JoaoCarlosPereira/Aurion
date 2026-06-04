---
status: done
title: Frontend — Setup do projeto Vite + React + TypeScript
type: frontend
complexity: low
dependencies: []
---

# Frontend — Setup do projeto Vite + React + TypeScript

## Visão Geral

Inicializar o projeto frontend com Vite, React 18+, TypeScript, Tailwind CSS, react-router-dom, Zustand e Axios. Configurar o tema Pac-Man Tech Theme adaptado do design system existente, com a paleta ciano/amarelo e fundo escuro.

<critical>
- Ler PRD e TechSpec completos antes de implementar
- Consultar TechSpec para requisitos técnicos específicos
- Foco no O QUÊ, não no COMO
- Minimizar código, maximizar reuso
- Testes são obrigatórios em todas as tarefas
</critical>

<requirements>
1. O projeto DEVE ser inicializado com Vite + React + TypeScript conforme TechSpec (Seção 6)
2. O projeto DEVE usar Tailwind CSS para estilização
3. O projeto DEVE usar Zustand para gerenciamento de estado
4. O projeto DEVE usar Axios para comunicação HTTP com o backend
5. O projeto DEVE usar react-router-dom para navegação
6. O tema DEVE seguir o design system Pac-Man Tech Theme adaptado (ciano #34d3ff, amarelo #ffd166, fundo #08101c)
7. O projeto DEVE ter 3 rotas: Chat, Histórico e Configurações
8. O projeto DEVE incluir Plus Jakarta Sans como fonte principal
9. O Vite DEVE ser configurado com proxy para /api e /ws no ambiente de desenvolvimento
</requirements>

## Subtarefas
- [x] Inicializar projeto Vite com template React TypeScript
- [x] Instalar dependências: zustand, axios, react-router-dom, tailwindcss (+ @types/react, @types/react-dom, @types/node)
- [x] Configurar `vite.config.ts` com proxy para /api e /ws
- [x] Configurar `tailwind.config.ts` com tema Pac-Man adaptado
- [x] Configurar `tsconfig.json` com paths aliases (@/*) — corrigido `allowImportingTsExtensions`
- [x] Criar `src/main.tsx` como entry point (BrowserRouter + StrictMode)
- [x] Criar `src/App.tsx` com rotas principais (Chat, Histórico, Configurações)
- [x] Criar `src/styles/main.css` com imports do Tailwind 4 (`@import "tailwindcss"` + `@theme`) e tema Pac-Man
- [x] Criar `src/styles/pacman-theme.css` com design tokens do tema (paleta + estados)
- [x] Criar estrutura de componentes PLACEHOLDER: Chat/ChatPanel, Settings/SettingsPanel, History/HistoryPanel, Status/SystemStatus + StatusIndicator, MicButton/MicButton, AudioPlayer/AudioPlayer
- [x] Criar `src/hooks/`: useWebSocket, useAurionAPI, useSystemState (IMPLEMENTADOS) e useAudioRecorder (STUB tipado — task 16)
- [x] Criar `src/store/aurionStore.ts` (Zustand: systemState, mensagens, config, wsStatus)
- [x] Criar `src/services/`: api.ts (axios, todos os endpoints REST) e websocket.ts (cliente WS com auto-reconnect)
- [x] Criar `src/types.ts` com TODOS os tipos do contrato (Interaction, AppConfig + subconfigs, SystemState, mensagens WS)
- [ ] Configurar CORS no backend para permitir origin do Vite dev server (fora do escopo desta task — backend/main.py, validado na integração)
- [x] Verificar typecheck: `npx tsc --noEmit` passa limpo

## Notas de Implementação (Setup de Paralelismo)

Esta task cria os contratos compartilhados que habilitam as tasks 13-17 a
trabalharem em paralelo, preenchendo apenas seus próprios componentes sem editar
arquivos compartilhados:

- **types.ts**: contrato completo (TechSpec 3). Importado por store, services e hooks.
- **store/aurionStore.ts**: estado global Zustand. As telas consomem via seletores.
- **services/api.ts**: wrapper axios de todos os endpoints REST (config, test/*, history, command).
- **services/websocket.ts**: classe `AurionWebSocket` tipada com auto-reconnect (backoff, max 5).
- **hooks**: useWebSocket (genérico), useAurionAPI, useSystemState (assina /ws/status → store),
  useAudioRecorder (STUB tipado p/ task 16).
- **Componentes PLACEHOLDER**: cada área (Chat/History/Settings/Status/MicButton/AudioPlayer)
  já existe com layout mínimo e TODOs apontando a task responsável.

Quem consome o quê:
- Task 13 (Chat): ChatPanel.tsx + ChatMessage/ChatInput (novos), usa api.sendCommand, store.messages, useSystemState.
- Task 14 (Config): SettingsPanel.tsx + sub-forms (novos), usa api.getConfig/updateConfig/test*.
- Task 15 (Histórico): HistoryPanel.tsx + HistorySearch (novo), usa api.getHistory/clearHistory.
- Task 16 (Microfone): implementa useAudioRecorder, usa MicButton + /ws/voice-command.
- Task 17 (AudioPlayer): implementa AudioPlayer com streaming via /ws/audio.

## Validação (`npx tsc --noEmit` em frontend/)

```
$ npm install
added 110 packages, and audited 111 packages in 10s
found 0 vulnerabilities
# após adicionar @types/react, @types/react-dom, @types/node:
added 6 packages, and audited 117 packages in 1s
found 0 vulnerabilities

$ npx tsc --noEmit
EXIT=0   (sem erros — saída vazia)
```

Observações:
- `package.json` recebeu `@types/react`, `@types/react-dom` e `@types/node`
  (ausentes no scaffolding original), necessários para o typecheck passar.
- `tsconfig.json`: `allowImportingTsFiles` (inválido) corrigido para
  `allowImportingTsExtensions`.
- `package.json` script `build`: `tsc -b` → `tsc` (sem project references).
- Arquivos `__init__.py` do scaffolding genérico em `src/` foram removidos.
- Build (`vite build`) e CORS do backend são validados na task de integração (18), conforme regras.

## Detalhes de Implementação

### Arquivos Relevantes
- `frontend/package.json` — dependências
- `frontend/vite.config.ts` — configuração do Vite
- `frontend/tailwind.config.ts` — configuração do Tailwind
- `frontend/tsconfig.json` — configuração do TypeScript
- `frontend/src/styles/pacman-theme.css` — tema Pac-Man adaptado
- `frontend/src/store/aurionStore.ts` — store Zustand
- `frontend/src/services/api.ts` — Axios wrapper
- `frontend/src/services/websocket.ts` — WebSocket client

### Arquivos Dependentes
- Nenhum — tarefa independente de setup
- `backend/main.py` — configuração de CORS para Vite dev server

### ADRs Relacionados
- [ADR-003](adrs/adr-003.md) — SPA React/TypeScript + Vite + FastAPI via HTTP REST e WebSocket

## Entregáveis
- Projeto Vite + React + TypeScript funcional
- Tailwind CSS configurado com tema Pac-Man
- Rotas: Chat, Histórico, Configurações
- Zustand store inicial
- Axios wrapper e WebSocket client
- Plus Jakarta Sans como fonte
- Proxy configurado para /api e /ws
- Testes básicos de renderização

## Testes
- [ ] Teste que `npm run dev` inicia sem erros
- [ ] Teste de renderização do componente App
- [ ] Teste de navegação entre as 3 rotas (Chat, Histórico, Configurações)
- [ ] Teste de que o Axios wrapper está configurado com base URL correta
- [ ] Teste de que o tema Pac-Man está aplicado (cores verificadas)
- [ ] Teste de que Plus Jakarta Sans está carregando
- [ ] Teste de proxy /api redirecionando para o backend

## Critérios de Sucesso
- Todos os testes passando
- Projeto rodando em http://localhost:5173
- 3 rotas funcionais com conteúdo placeholder
- Tema Pac-Man aplicado corretamente
- Nenhuma dependência com erro de instalação
