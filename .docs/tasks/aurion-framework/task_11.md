---
status: completed
title: API REST completa — Endpoints de teste e configurações avançadas
type: backend
complexity: medium
dependencies: ["task_05"]
---

# API REST completa — Endpoints de teste e configurações avançadas

## Visão Geral

Completar a API REST com os endpoints de teste de conexão (POST /api/test/*) para Hermes, STT e TTS, além de endpoints avançados de configurações. Esta tarefa garante que o frontend possa validar conexões e configurações diretamente do painel de configurações.

<critical>
- Ler PRD e TechSpec completos antes de implementar
- Consultar TechSpec para requisitos técnicos específicos
- Foco no O QUÊ, não no COMO
- Minimizar código, maximizar reuso
- Testes são obrigatórios em todas as tarefas
</critical>

<requirements>
1. O endpoint `POST /api/test/hermes` DEVE testar conexão com o Hermes Agent
2. O endpoint `POST /api/test/stt` DEVE testar conexão/funcionamento do serviço STT
3. O endpoint `POST /api/test/tts` DEVE testar conexão/funcionamento do serviço TTS
4. Cada endpoint DEVE retornar o resultado do teste com status e mensagem descritiva
5. O teste de TTS DEVE incluir teste de streaming para verificar funcionamento do TTS externo
6. Os endpoints DEVE ser protegidos contra execução indesejada (rate limiting básico)
7. O sistema DEVE suportar configurações avançadas de audio (sample_rate, channels, chunk_size, silence_threshold)
</requirements>

## Subtarefas
- [x] Criar `backend/api/test.py` com endpoints de teste
- [x] Implementar POST /api/test/hermes — testar conexão com Hermes
- [x] Implementar POST /api/test/stt — testar conexão/funcionamento do STT
- [x] Implementar POST /api/test/tts — testar conexão/funcionamento do TTS
- [x] Implementar teste de streaming para TTS externo
- [x] Implementar rate limiting básico nos endpoints de teste (janela deslizante)
- [x] Implementar retorno estruturado com status, mensagem e detalhes
- [x] Implementar endpoint para listar vozes disponíveis do TTS (GET /api/test/tts/voices)
- [x] Implementar endpoint para reset de configurações (POST /api/config/reset)
- [x] Registrar router no `backend/api/router.py`
- [x] Criar testes unitários para cada endpoint de teste
- [x] Criar testes de integração

## Detalhes de Implementação

### Arquivos Relevantes
- `backend/api/test.py` — endpoints de teste (388 linhas)
- `backend/api/config.py` — configurações avançadas (153 linhas)

### Arquivos Dependentes
- `backend/svc/hermes_bridge.py` — dependência: teste de conexão
- `backend/svc/stt.py` — dependência: teste de STT
- `backend/svc/tts.py` — dependência: teste de TTS
- `backend/config/settings.py` — dependência: reset de configurações

### ADRs Relacionados
- [ADR-002](adrs/adr-002.md) — FastAPI para endpoints REST

## Entregáveis
- Endpoints POST /api/test/* completos (hermes, stt, tts)
- Teste de streaming para TTS
- Rate limiting nos endpoints de teste (rate limiter com janela deslizante)
- Endpoint de listagem de vozes (GET /api/test/tts/voices)
- Endpoint de reset de configurações (POST /api/config/reset)
- Testes unitários e de integração
- Cobertura de código >= 80%

## Testes
- [x] Teste de POST /api/test/hermes com Hermes disponível (sucesso)
- [x] Teste de POST /api/test/hermes com Hermes indisponível (erro)
- [x] Teste de POST /api/test/stt com STT disponível (sucesso)
- [x] Teste de POST /api/test/stt com modelo inexistente (erro)
- [x] Teste de POST /api/test/tts com edge-tts disponível (sucesso)
- [x] Teste de POST /api/test/tts com TTS externo e streaming (sucesso)
- [x] Teste de POST /api/test/tts com TTS externo indisponível (fallback edge-tts)
- [x] Teste de rate limiting nos endpoints de teste
- [x] Teste de endpoint de listagem de vozes
- [x] Teste de endpoint de reset de configurações

## Critérios de Sucesso
- Todos os testes passando
- Cobertura >= 80%
- Endpoints seguindo a TechSpec (Seção 3.1)
- Teste de streaming para TTS funcionando
- Rate limiting ativo nos endpoints de teste
