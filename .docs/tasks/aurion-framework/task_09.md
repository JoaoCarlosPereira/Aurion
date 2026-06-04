---
status: completed
title: Listening Service — Loop principal de escuta
type: backend
complexity: high
dependencies: ["task_06", "task_07", "task_08"]
---

# Listening Service — Loop principal de escuta

## Visão Geral

Implementar o serviço principal que opera em thread dedicada, operando em loop contínuo: captura de áudio via PyAudio, detecção do wake word, captura de fala até silêncio, conversão STT, envio ao Hermes Bridge, síntese TTS e roteamento da resposta. Este é o cérebro do sistema Aurion.

<critical>
- Ler PRD e TechSpec completos antes de implementar
- Consultar TechSpec para requisitos técnicos específicos
- Foco no O QUÊ, não no COMO
- Minimizar código, maximizar reuso
- Testes são obrigatórios em todas as tarefas
</critical>

<requirements>
1. O módulo `svc/listening.py` DEVE implementar um loop contínuo em thread dedicada
2. O loop DEVE seguir o fluxo da TechSpec (Seção 5.1): PyAudio → Wake Word → STT → Hermes → TTS → Roteamento → Banco
3. O serviço DEVE usar PyAudio para captura de áudio em 16kHz, 1 canal
4. O serviço DEVE notificar o estado via WebSocket (listening, detecting, stt, processing, tts)
5. O serviço DEVE usar VAD (Voice Activity Detection) para detectar 1-3s de silêncio
6. O roteamento da resposta DEVE usar reprodução progressiva do TTS externo — começar a tocar enquanto ainda está recebendo chunks
7. O serviço DEVE salvar cada interação no banco de dados após processamento
8. O serviço DEVE suportar start/stop/graceful shutdown
</requirements>

## Subtarefas
- [x] Criar `backend/svc/listening.py` com classe ListeningService
- [x] Implementar loop principal em thread dedicada
- [x] Implementar captura de áudio via PyAudio (16kHz, 1 canal)
- [x] Implementar integração com WakeWordEngine
- [x] Implementar captura de fala após wake word até silêncio (VAD)
- [x] Implementar integração com STTService
- [x] Implementar integração com HermesBridge
- [x] Implementar integração com TTSService usando streaming progressivo
- [x] Implementar roteamento de resposta (local: speaker / web: WebSocket)
- [x] Implementar notificação de estado via WebSocket broadcasts
- [x] Implementar salvamento no banco de dados após processamento
- [x] Implementar gerenciamento de ciclo de vida (start/stop/shutdown)
- [x] Implementar tratamento de exceções em cada etapa do pipeline
- [x] Implementar métricas de latência por etapa
- [x] Criar testes unitários com mocks de cada serviço
- [x] Criar teste de integração do pipeline completo (mock)

## Detalhes de Implementação

### Arquivos Relevantes
- `backend/svc/listening.py` — loop principal de escuta (636 linhas, maior módulo do backend)
- `backend/svc/wakeword.py` — dependência: wake word engine
- `backend/svc/stt.py` — dependência: STT service
- `backend/svc/hermes_bridge.py` — dependência: Hermes bridge
- `backend/svc/tts.py` — dependência: TTS service

### Arquivos Dependentes
- `backend/api/websocket.py` — broadcasts de estado via WebSocket
- `backend/db/repo.py` — persistência de interações
- `backend/main.py` — injeção de dependência

### ADRs Relacionados
- [ADR-002](adrs/adr-002.md) — Threads separadas para captura de áudio (mitigação do GIL)

## Entregáveis
- ListeningService completo com loop em thread dedicada
- Pipeline completo: captura → wake word → STT → Hermes → TTS → roteamento → banco
- Notificações de estado via WebSocket
- Reprodução progressiva do TTS externo
- Testes unitários e de integração
- Cobertura de código >= 80%

## Testes
- [x] Teste de inicialização do loop em thread dedicada
- [x] Teste de captura de áudio via PyAudio (mock)
- [x] Teste de detecção de wake word acionando o pipeline
- [x] Teste de VAD detectando silêncio e encerrando captura
- [x] Teste de pipeline completo: wake word → STT → Hermes → TTS → banco
- [x] Teste de notificação de estado via WebSocket (listening, detecting, stt, processing, tts)
- [x] Teste de roteamento de resposta local (speaker)
- [x] Teste de roteamento de resposta web (WebSocket)
- [x] Teste de salvamento no banco de dados
- [x] Teste de graceful shutdown
- [x] Teste de tratamento de erro no pipeline (continua após falha)
- [x] Teste de medição de latência por etapa

## Critérios de Sucesso
- Todos os testes passando
- Cobertura >= 80%
- Pipeline completo funcionando conforme TechSpec (Seção 5.1)
- Loop operando em thread dedicada sem bloquear o FastAPI
- Notificações de estado enviadas via WebSocket
- Reprodução progressiva do TTS funcionando
