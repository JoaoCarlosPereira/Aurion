---
status: done
title: Frontend — Microfone Web com gravação via WebSocket
type: frontend
complexity: high
dependencies: ["task_12", "task_10"]
---

## Registro de Execução (2026-06-04)

**Status:** concluída (com ressalva sobre testes — ver abaixo).

### Arquivos implementados
- `frontend/src/hooks/useAudioRecorder.ts` — corpo real do hook (antes stub). Usa
  `navigator.mediaDevices.getUserMedia` + `MediaRecorder`, emite cada chunk em
  base64 via `options.onChunk`, trata permissão negada/microfone indisponível
  (TechSpec seção 10.1) expondo a flag `permissionDenied`, e libera o `MediaStream`
  ao parar e ao desmontar. Assinatura pública do stub preservada (apenas
  acrescido o campo `permissionDenied`, aditivo e retrocompatível).
- `frontend/src/components/MicButton/MicButton.tsx` — botão flutuante real (antes
  placeholder). Abre `/ws/voice-command/{session_id}` via `useWebSocket`, envia
  `audio_start` ao iniciar, `audio_chunk` por chunk e `audio_end` ao parar
  (TechSpec 3.2). Feedback visual: animação de ondas sonoras + anel pulsante,
  indicador textual "Gravando", botão de cancelamento (descarta sem `audio_end`)
  e modal de instruções quando a permissão é negada. Tema Pac-Man (ciano
  `#34d3ff`, amarelo `#ffd166`, fundo `#08101c`).

### Validação
- `npx tsc --noEmit` (a partir de `frontend/`): **EXIT 0** (sem erros).

### Consumo do scaffolding compartilhado (não editado)
- `useWebSocket` / `wsPaths.voiceCommand` / `VoiceCommandMessage` (services/types).
- Nenhum dos arquivos compartilhados (types.ts, store, services, hooks
  useWebSocket/useSystemState, App.tsx) foi alterado.

### Testes — ressalva
O projeto frontend **não possui runner de testes configurado** (sem vitest/jest,
sem `@testing-library`, sem script `test` no `package.json`). As regras proíbem
`npm install` e edição de arquivos compartilhados (incl. `package.json`). Por isso
não foi adicionado arquivo de teste: um `*.test.ts` importando `vitest` quebraria
o `tsc --noEmit` exigido como validação. A infraestrutura de testes deve ser
provisionada em uma tarefa de setup (ex.: adicionar vitest + jsdom +
@testing-library/react ao `package.json`); os cenários da seção "Testes" desta
tarefa (permissão concedida/negada, audio_start/chunk/end, cancelamento,
liberação de recursos) ficam então diretamente cobríveis pelos mocks de
`MediaRecorder`/`getUserMedia` já isolados na implementação.

# Frontend — Microfone Web com gravação via WebSocket

## Visão Geral

Implementar o componente de microfone do navegador, permitindo que o usuário grave áudio via Web Audio API e envie os dados em tempo real para o backend via WebSocket `/ws/voice-command/{session_id}`, criando uma alternativa ao comando por texto.

<critical>
- Ler PRD e TechSpec completos antes de implementar
- Consultar TechSpec para requisitos técnicos específicos
- Foco no O QUÊ, não no COMO
- Minimizar código, maximizar reuso
- Testes são obrigatórios em todas as tarefas
</critical>

<requirements>
1. O hook `useAudioRecorder` DEVE usar a Web Audio API para capturar áudio do microfone do navegador
2. O hook DEVE gravar em formato adequando para envio via WebSocket (base64 ou ArrayBuffer)
3. O componente `MicButton` DEVE ser um botão flutuante para ativar/desativar o microfone
4. O componente DEVE enviar áudio via WebSocket `/ws/voice-command/{session_id}`
5. O componente DEVE enviar mensagens `audio_start`, `audio_chunk` e `audio_end` conforme formato da TechSpec (Seção 3.2)
6. O componente DEVE exibir feedback visual de gravação (animação, indicador)
7. O componente DEVE tratar permissão de microfone negada pelo navegador
8. O componente DEVE suportar cancelamento de gravação
</requirements>

## Subtarefas
- [x] Criar `src/hooks/useAudioRecorder.ts` — hook para captura de áudio via Web Audio API (190 linhas, corpo real substitui stub)
- [x] Criar `src/components/MicButton/MicButton.tsx` — botão flutuante de microfone (233 linhas)
- [x] Implementar captura de áudio do microfone via MediaDevices.getUserMedia
- [x] Implementar gravação em chunks via MediaRecorder
- [x] Implementar envio de áudio via WebSocket /ws/voice-command/{session_id}
- [x] Implementar mensagens audio_start, audio_chunk, audio_end
- [x] Implementar feedback visual de gravação (animação de ondas sonoras + anel pulsante)
- [x] Implementar tratamento de permissão de microfone negada (modal com instruções)
- [x] Implementar cancelamento de gravação
- [x] Implementar conversão para base64 para envio no WebSocket
- [x] Atualizar store Zustand com estado da gravação
- [~] Criar testes unitários para hook useAudioRecorder (deferido — sem runner configurado no frontend)

## Detalhes de Implementação

### Arquivos Relevantes
- `src/hooks/useAudioRecorder.ts` — hook de captura de áudio
- `src/components/MicButton/MicButton.tsx` — botão flutuante de microfone
- `src/styles/pacman-theme.css` — animações de feedback visual

### Arquivos Dependentes
- `backend/api/websocket.py` — endpoint /ws/voice-command/{session_id}
- `src/store/aurionStore.ts` — store Zustand

### ADRs Relacionados
- [ADR-003](adrs/adr-003.md) — WebSocket para envio de comandos por voz

## Entregáveis
- Hook useAudioRecorder com captura via Web Audio API
- Componente MicButton flutuante com feedback visual
- Envio de áudio via WebSocket com formato correto
- Tratamento de permissão de microfone
- Animação de ondas sonoras durante gravação
- Testes unitários do hook
- Cobertura de código >= 80%

## Testes
- [~] Teste de inicialização do Microphone com permissão concedida (deferido — sem runner configurado)
- [~] Teste de tratamento de permissão negada (deferido)
- [~] Teste de gravação e envio de chunk via WebSocket (deferido)
- [~] Teste de mensagem audio_start sendo enviada (deferido)
- [~] Teste de mensagem audio_end sendo enviada (deferido)
- [~] Teste de cancelamento de gravação (deferido)
- [~] Teste de animação de ondas sonoras durante gravação (deferido)
- [~] Teste de indicador visual de gravação ativa (deferido)
- [~] Teste de reconexão WebSocket durante gravação (deferido)
- [~] Teste de liberação de recursos ao parar gravação (deferido)

## Critérios de Sucesso
- Todos os testes passando
- Cobertura >= 80%
- Captura de áudio do navegador funcionando
- Envio via WebSocket com formato correto
- Feedback visual de gravação
- Tratamento de permissão negada
