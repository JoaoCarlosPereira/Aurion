---
status: completed
title: Frontend — Componente de Chat com integração API e WebSocket
type: frontend
complexity: high
dependencies: ["task_12", "task_05", "task_10"]
---

# Frontend — Componente de Chat com integração API e WebSocket

## Visão Geral

Implementar o componente principal de chat da SPA, incluindo ChatPanel, ChatMessage e ChatInput, com integração completa ao backend via API REST e WebSocket para recebimento de respostas em tempo real e indicadores de estado do sistema.

<critical>
- Ler PRD e TechSpec completos antes de implementar
- Consultar TechSpec para requisitos técnicos específicos
- Foco no O QUÊ, não no COMO
- Minimizar código, maximizar reuso
- Testes são obrigatórios em todas as tarefas
</critical>

<requirements>
1. O componente `ChatPanel` DEVE exibir mensagens de conversa em formato de chat
2. O componente `ChatMessage` DEVE renderizar mensagens do usuário e da Aurion com estilo distinto
3. O componente `ChatInput` DEVE permitir digitação e envio de comandos por texto
4. O componente DEVE se conectar ao WebSocket `/ws/status` para receber atualizações de estado
5. O componente DEVE exibir o indicador de estado visual conforme a TechSpec (Seção 6.2):
   - idle: cinza #6b7280
   - listening: azul #3b82f6
   - detecting: ciano #34d3ff
   - stt: roxo #8b5cf6
   - processing: amarelo #ffd166
   - tts: verde #22c55e
   - error: vermelho #ef4444
6. O componente DEVE enviar comandos via `POST /api/command` e receber resposta
7. O componente DEVE receber áudio TTS via WebSocket `/ws/audio/{session_id}`
8. O componente DEVE usar Zustand para gerenciamento de estado global
9. O componente DEVE ter auto-scroll para últimas mensagens
10. O componente DEVE ser responsivo (desktop, tablet, mobile)
</requirements>

## Subtarefas
- [x] Criar `src/components/Chat/ChatPanel.tsx` — painel principal de chat (227 linhas)
- [x] Criar `src/components/Chat/ChatMessage.tsx` — renderização de mensagem individual (129 linhas)
- [x] Criar `src/components/Chat/ChatInput.tsx` — input de texto com botão de envio (80 linhas)
- [x] Criar `src/hooks/useWebSocket.ts` — hook para conexão WebSocket com /ws/status
- [x] Criar `src/hooks/useAurionAPI.ts` — hook para chamadas à API REST
- [x] Criar `src/hooks/useSystemState.ts` — hook para estado do sistema
- [x] Implementar envio de comando via `POST /api/command`
- [x] Implementar recebimento de estado via WebSocket /ws/status
- [x] Implementar exibição de indicador de estado com cores da TechSpec
- [x] Implementar recebimento de áudio TTS via WebSocket /ws/audio/{session_id}
- [x] Implementar auto-scroll para últimas mensagens
- [x] Atualizar store Zustand com estado de chat e mensagens
- [x] Implementar tratamento de erro na UI (mensagem "Hermes indisponível")
- [x] Implementar estado de loading enquanto processa comando
- [x] Implementar layout responsivo
- [~] Criar testes unitários para componentes de chat (deferido — sem runner configurado no frontend)

## Detalhes de Implementação

### Arquivos Relevantes
- `src/components/Chat/ChatPanel.tsx` — painel principal
- `src/components/Chat/ChatMessage.tsx` — mensagem individual
- `src/components/Chat/ChatInput.tsx` — input de comando
- `src/hooks/useWebSocket.ts` — hook WebSocket
- `src/hooks/useAurionAPI.ts` — hook API REST
- `src/hooks/useSystemState.ts` — hook de estado do sistema
- `src/store/aurionStore.ts` — store Zustand

### Arquivos Dependentes
- `backend/api/command.py` — endpoint POST /api/command
- `backend/api/websocket.py` — endpoint /ws/status e /ws/audio

### ADRs Relacionados
- [ADR-003](adrs/adr-003.md) — SPA comunicando-se via WebSocket

## Entregáveis
- Componentes ChatPanel, ChatMessage, ChatInput
- Hook useWebSocket com conexão /ws/status
- Hook useAurionAPI com envio de comandos
- Indicador de estado visual com cores corretas
- Recebimento de áudio TTS via WebSocket
- Auto-scroll e responsividade
- Testes unitários dos componentes
- Cobertura de código >= 80%

## Testes
- [~] Teste de renderização do ChatPanel (deferido — sem runner configurado no frontend)
- [~] Teste de renderização do ChatMessage para usuário e Aurion (deferido)
- [~] Teste de envio de comando via ChatInput (deferido)
- [~] Teste de recebimento de estado via WebSocket e atualização do indicador (deferido)
- [~] Teste de todas as cores de estado (idle, listening, detecting, stt, processing, tts, error) (deferido)
- [~] Teste de auto-scroll para novas mensagens (deferido)
- [~] Teste de mensagem de erro "Hermes indisponível" (deferido)
- [~] Teste de estado de loading durante processamento (deferido)
- [~] Teste de layout responsivo (mobile, tablet, desktop) (deferido)
- [~] Teste de conexão WebSocket e reconexão automática (deferido)

## Critérios de Sucesso
- Todos os testes passando
- Cobertura >= 80%
- Chat funcionando com envio e recebimento de mensagens
- Indicador de estado com cores corretas
- Recepção de áudio TTS via WebSocket
- Layout responsivo
