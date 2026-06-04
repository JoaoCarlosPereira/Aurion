---
status: completed
title: Hermes Bridge — Cliente HTTP para Hermes Agent
type: backend
complexity: medium
dependencies: ["task_03"]
---

# Hermes Bridge — Cliente HTTP para Hermes Agent

## Visão Geral

Implementar o cliente HTTP para comunicação com o Hermes Agent, responsável por enviar comandos e receber respostas. O Hermes Bridge deve implementar retry com backoff exponencial, tratamento de erros robusto e uso do httpx como cliente HTTP assíncrono.

<critical>
- Ler PRD e TechSpec completos antes de implementar
- Consultar TechSpec para requisitos técnicos específicos
- Foco no O QUÊ, não no COMO
- Minimizar código, maximizar reuso
- Testes são obrigatórios em todas as tarefas
</critical>

<requirements>
1. O módulo `svc/hermes_bridge.py` DEVE usar httpx como cliente HTTP assíncrono
2. O Hermes Bridge DEVE ler as configurações do Hermes (endpoint, auth_token) do Config Manager
3. O Hermes Bridge DEVE implementar retry com backoff exponencial (3 tentativas, conforme TechSpec Seção 10.1)
4. O Hermes Bridge DEVE enviar header `Authorization` com o token configurado
5. O Hermes Bridge DEVE expor um método para envio de comandos ao endpoint configurável do Hermes
6. O Hermes Bridge DEVE tratar erros HTTP (4xx, 5xx) e exceções de rede
7. O Hermes Bridge DEVE retornar estrutura de resposta padronizada contendo a resposta do Hermes
8. Em caso de falha após retries, o Hermes Bridge DEVE lançar exceção com código de erro claro
</requirements>

## Subtarefas
- [x] Criar `backend/svc/__init__.py` com inicialização dos serviços
- [x] Criar `backend/svc/hermes_bridge.py` com classe HermesBridge
- [x] Implementar método `send_command(message: str)` — POST ao endpoint do Hermes
- [x] Implementar método `test_connection()` — teste de conectividade com o Hermes
- [x] Implementar retry com backoff exponencial (3 tentativas)
- [x] Implementar tratamento de erros HTTP (4xx, 5xx)
- [x] Implementar tratamento de exceções de rede (timeout, connection error)
- [x] Implementar header Authorization com token da configuração
- [x] Implementar parser da resposta do Hermes
- [x] Implementar estrutura de erro conforme TechSpec (Seção 10.2) — APIError
- [x] Criar testes unitários com mocks para httpx
- [x] Criar teste de retry e backoff exponencial
- [x] Criar teste de tratamento de erros (404, 500, timeout)

## Detalhes de Implementação

### Arquivos Relevantes
- `backend/svc/hermes_bridge.py` — cliente HTTP para Hermes Agent
- `backend/models/response.py` — modelos de resposta da API

### Arquivos Dependentes
- `backend/config/settings.py` — leitura das configurações do Hermes
- `backend/api/command.py` — consumo do Hermes Bridge
- `backend/api/test.py` — endpoint de teste de conexão

### ADRs Relacionados
- [ADR-002](adrs/adr-002.md) — httpx como cliente HTTP assíncrono
- [ADR-002](adrs/adr-002.md) — FastAPI para endpoints REST

## Entregáveis
- Módulo Hermes Bridge completo com retry e tratamento de erros
- Método de envio de comandos ao Hermes Agent
- Método de teste de conexão
- Estrutura de erros padronizada
- Testes unitários e de integração
- Cobertura de código >= 80%

## Testes
- [x] Teste de envio de comando com resposta 200 do Hermes
- [x] Teste de retry com backoff exponencial (falha 3x)
- [x] Teste de erro HTTP 401 (unauthorized)
- [x] Teste de erro HTTP 500 (server error)
- [x] Teste de timeout de conexão
- [x] Teste de conexão recusada (connection error)
- [x] Teste de test_connection() retornando sucesso
- [x] Teste de test_connection() falhando com erro correto
- [x] Teste de header Authorization sendo enviado corretamente
- [x] Teste de parsing da resposta do Hermes

## Notas de Implementação

- `backend/svc/hermes_bridge.py`: classe `HermesBridge` (httpx async), com
  `send_command` (POST `/api/completion`) e `test_connection` (GET `/health`).
  Retry com backoff exponencial (`DEFAULT_MAX_RETRIES=3`, base 0.5s, fator 2.0).
  Erros 4xx (exceto 429) são definitivos (sem retry); 5xx/429/timeout/conexão
  são transitórios (com retry). Erros convertidos em `HermesError` carregando
  um `APIError` padronizado. `httpx` é importado de forma lazy; o cliente é
  criado em `_create_client` (ponto de mock nos testes).
- `backend/models/response.py`: modelos `APIError` (TechSpec Seção 10.2) e
  `HermesResponse` (resposta padronizada).
- `backend/api/test.py`: `router` (APIRouter) expondo `POST /api/test/hermes`,
  com dependências `get_config_manager_dep` e `get_hermes_bridge_factory`
  sobrescritíveis via `app.dependency_overrides`. NÃO faz wiring em
  `main.py`/`router.py` (reservado à task_18).
- Testes em `backend/tests/test_hermes.py`: 22 testes, sem rede real
  (`httpx.MockTransport` + `asyncio.sleep` stubado). Cobertura 95% nos módulos
  `svc/hermes_bridge.py` e `api/test.py`.

## Critérios de Sucesso
- Todos os testes passando
- Cobertura >= 80%
- Retry com backoff exponencial funcionando corretamente
- Tratamento de erros conforme TechSpec (Seção 10.1 e 10.2)
- Estrutura de resposta padronizada
