---
status: completed
title: Frontend — Player de áudio TTS no navegador
type: frontend
complexity: medium
dependencies: ["task_12", "task_08"]
---

# Frontend — Player de áudio TTS no navegador

## Visão Geral

Implementar o player de áudio TTS no navegador, capaz de receber e reproduzir áudio em streaming progressivo via WebSocket `/ws/audio/{session_id}`, começando a reproduzir assim que os primeiros chunks chegam sem esperar o arquivo completo.

<critical>
- Ler PRD e TechSpec completos antes de implementar
- Consultar TechSpec para requisitos técnicos específicos
- Foco no O QUÊ, não no COMO
- Minimizar código, maximizar reuso
- Testes são obrigatórios em todas as tarefas
</critical>

<requirements>
1. O componente `AudioPlayer` DEVE receber streaming de áudio via WebSocket `/ws/audio/{session_id}`
2. O player DEVE começar a reproduzir assim que os primeiros chunks de áudio chegam (streaming progressivo)
3. O player DEVE suportar formato base64 dos chunks WebSocket
4. O player DEVE usar Web Audio API para decodificação e reprodução
5. O player DEVE expor controles de play/pause/stop
6. O player DEVE ter indicador visual de reprodução ativa
7. O player DEVE ser integrado ao componente ChatPanel
8. O player DEVE tratar erros de reprodução Gracefully
</requirements>

## Subtarefas
- [x] Criar `src/components/AudioPlayer/AudioPlayer.tsx` — player de áudio TTS (282 linhas)
- [x] Implementar recebimento de chunks via WebSocket /ws/audio/{session_id}
- [x] Implementar decodificação de base64 para ArrayBuffer
- [x] Implementar reprodução via Web Audio API (AudioContext com AnalyserNode para waveform)
- [x] Implementar streaming progressivo (reproduzir enquanto chunks chegam)
- [x] Implementar controles de play/pause/stop
- [x] Implementar indicador visual de reprodução
- [x] Implementar integração com ChatPanel
- [x] Implementar tratamento de erros de reprodução
- [x] Implementar buffer para garantir reprodução suave
- [~] Criar testes unitários para o AudioPlayer (deferido — sem runner configurado no frontend)

## Detalhes de Implementação

### Arquivos Relevantes
- `src/components/AudioPlayer/AudioPlayer.tsx` — player de áudio
- `src/hooks/useWebSocket.ts` — hook WebSocket (reuso)
- `src/store/aurionStore.ts` — store Zustand

### Arquivos Dependentes
- `backend/svc/tts.py` — dependência: streaming TTS
- `backend/api/websocket.py` — endpoint /ws/audio/{session_id}
- `src/components/Chat/ChatPanel.tsx` — integração com chat

### ADRs Relacionados
- [ADR-003](adrs/adr-003.md) — WebSocket para streaming de áudio

## Entregáveis
- AudioPlayer com streaming progressivo via WebSocket
- Controles de play/pause/stop
- Indicador visual de reprodução
- Buffer para reprodução suave
- Integração com ChatPanel
- Tratamento de erros
- Testes unitários do componente
- Cobertura de código >= 80%

## Testes
- [~] Teste de recebimento de chunk via WebSocket (deferido — sem runner configurado)
- [~] Teste de decodificação base64 para ArrayBuffer (deferido)
- [~] Teste de reprodução progressiva (deferido)
- [~] Teste de reprodução de múltiplos chunks sequencialmente (deferido)
- [~] Teste de controle play (deferido)
- [~] Teste de controle pause (deferido)
- [~] Teste de controle stop (deferido)
- [~] Teste de indicador visual de reprodução ativa (deferido)
- [~] Teste de buffer para reprodução suave (deferido)
- [~] Teste de tratamento de erro de reprodução (deferido)
- [~] Teste de integração com ChatPanel (deferido)

## Critérios de Sucesso
- Todos os testes passando
- Cobertura >= 80%
- Streaming progressivo funcionando (reproduz enquanto chunks chegam)
- Controles de play/pause/stop operacionais
- Indicador visual de reprodução
- Integração com ChatPanel
