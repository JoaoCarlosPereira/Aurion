---
status: completed
title: Servidor WebSocket — Status em tempo real e streaming de áudio
type: backend
complexity: high
dependencies: ["task_09", "task_05"]
---

# Servidor WebSocket — Status em real e streaming de áudio

## Visão Geral

Implementar os endpoints WebSocket para comunicação em tempo real entre o backend e o frontend: status do sistema, streaming de áudio TTS para o navegador, e envio de comandos por voz via WebSocket do navegador.

<critical>
- Ler PRD e TechSpec completos antes de implementar
- Consultar TechSpec para requisitos técnicos específicos
- Foco no O QUÊ, não no COMO
- Minimizar código, maximizar reuso
- Testes são obrigatórios em todas as tarefas
</critical>

<requirements>
1. O endpoint `/ws/status` DEVE enviar atualizações de estado do sistema (listening, detecting, stt, processing, tts, error)
2. O endpoint `/ws/audio/{session_id}` DEVE enviar streaming de áudio TTS para o browser
3. O endpoint `/ws/voice-command/{session_id}` DEVE receber áudio do browser e encaminhar ao pipeline de escuta
4. Os payloads DEVEM seguir o formato definido na TechSpec (Seção 3.2)
5. O WebSocket DEVE suportar reconexão automática com backoff exponencial (max 5 tentativas)
6. O streaming de áudio TTS via WebSocket DEVE ser eficiente com chunks progressivos
7. O sistema DEVE gerenciar múltiplas conexões WebSocket simultâneas
8. O sistema DEVE suportar o formato base64 para dados de áudio nos payloads
</requirements>

## Subtarefas
- [x] Criar `backend/api/websocket.py` com gerenciador de conexões WebSocket
- [x] Implementar endpoint `/ws/status` — broadcasting de estados do sistema
- [x] Implementar endpoint `/ws/audio/{session_id}` — streaming TTS para browser
- [x] Implementar endpoint `/ws/voice-command/{session_id}` — recebimento de áudio do browser
- [x] Implementar broadcasting de estados do Listening Service
- [x] Implementar envio de chunks de áudio TTS via WebSocket
- [x] Implementar gerenciamento de múltiplas conexões simultâneas
- [x] Implementar reconexão automática com backoff exponencial (max 5 tentativas)
- [x] Implementar serialização base64 para dados de áudio
- [x] Implementar cleanup de conexões desconectadas
- [x] Implementar validação de payloads
- [x] Integrar com o Listening Service para broadcasts
- [x] Criar testes unitários para cada endpoint WebSocket
- [x] Criar teste de múltiplas conexões simultâneas

## Detalhes de Implementação

### Arquivos Relevantes
- `backend/api/websocket.py` — endpoints WebSocket (366 linhas, WebSocketManager completo)
- `backend/svc/listening.py` — dependência: notificações de estado

### Arquivos Dependentes
- `backend/main.py` — registro dos WebSocket routes
- `backend/svc/tts.py` — dependência: streaming de áudio
- `backend/svc/listening.py` — dependência: pipeline de escuta

### ADRs Relacionados
- [ADR-003](adrs/adr-003.md) — WebSocket para comunicação em tempo real

## Entregáveis
- 3 endpoints WebSocket implementados e operacionais
- Broadcasting de estados do sistema em tempo real
- Streaming de áudio TTS via WebSocket com chunks progressivos
- Recebimento de áudio via WebSocket do browser
- Gerenciamento de múltiplas conexões
- Testes unitários e de integração
- Cobertura de código >= 80%

## Testes
- [x] Teste de conexão e envio de mensagem via `/ws/status`
- [x] Teste de broadcasting de estados para múltiplos clientes
- [x] Teste de envio de chunks de áudio via `/ws/audio/{session_id}`
- [x] Teste de recebimento de áudio via `/ws/voice-command/{session_id}`
- [x] Teste de payload base64 para dados de áudio
- [x] Teste de reconexão com backoff exponencial
- [x] Teste de múltiplas conexões simultâneas
- [x] Teste de cleanup de conexão desconectada
- [x] Teste de validação de payload inválido
- [x] Teste de estado "listening" sendo enviado corretamente
- [x] Teste de estado "processing" sendo enviado corretamente
- [x] Teste de estado "tts" sendo enviado corretamente

## Critérios de Sucesso
- Todos os testes passando
- Cobertura >= 80%
- Endpoints seguindo a TechSpec (Seção 3.2)
- Streaming de áudio TTS via WebSocket com chunks progressivos
- Múltiplas conexões simultâneas funcionando
- Reconexão automática funcionando
