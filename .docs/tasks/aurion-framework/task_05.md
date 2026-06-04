---
status: completed
title: API REST de comandos e histórico
type: backend
complexity: high
dependencies: ["task_02", "task_03", "task_04"]
---

# API REST de comandos e histórico

## Visão Geral

Implementar os endpoints REST principais para envio de comandos por texto e consulta de histórico de interações. Esta tarefa integra o Hermes Bridge com o banco de dados para criar o fluxo completo de envio de comando, execução no Hermes e armazenamento do resultado.

<critical>
- Ler PRD e TechSpec completos antes de implementar
- Consultar TechSpec para requisitos técnicos específicos
- Foco no O QUÊ, não no COMO
- Minimizar código, maximizar reuso
- Testes são obrigatórios em todas as tarefas
</critical>

<requirements>
1. O endpoint `POST /api/command` DEVE receber `{ "message": "comando do usuário" }` e encaminhar ao Hermes Agent
2. O endpoint `POST /api/command` DEVE retornar `{ "id": "...", "status": "processing" }` com ID da interação
3. O endpoint `GET /api/command/{id}` DEVE retornar o status/resposta da interação
4. O endpoint `GET /api/history?limit=50&offset=0&search=termo` DEVE listar interações paginadas com busca
5. O endpoint `GET /api/history/{id}` DEVE retornar interação específica
6. O endpoint `DELETE /api/history` DEVE limpar todo o histórico
7. Após envio ao Hermes, o resultado DEVE ser salvo no banco de dados via repository
8. O canal DEVE ser identificado como "web" para comandos via API REST
9. A duração do processamento DEVE ser medida em milissegundos
10. O sistema DEVE usar o modelo Interaction definido na TechSpec (Seção 3.3)
</requirements>

## Subtarefas
- [x] Criar `backend/models/interaction.py` com modelo Pydantic Interaction
- [x] Criar `backend/models/response.py` com modelos de resposta da API
- [x] Criar `backend/api/command.py` com endpoint POST /api/command
- [x] Implementar POST /api/command — receber mensagem, enviar ao Hermes, salvar no banco
- [x] Implementar GET /api/command/{id} — consultar status da interação
- [x] Implementar GET /api/history — listagem paginada com busca por texto
- [x] Implementar GET /api/history/{id} — busca por ID
- [x] Implementar DELETE /api/history — limpeza total do histórico
- [x] Implementar medição de duração em milissegundos
- [x] Implementar gerenciamento de estado da interação (processing → success/error)
- [x] Implementar tratamento de erros (Hermes indisponível, timeouts)
- [x] Registrar router no `backend/api/router.py`
- [x] Criar testes unitários para cada endpoint
- [x] Criar testes de integração com banco de dados em memória

## Detalhes de Implementação

### Arquivos Relevantes
- `backend/api/command.py` — endpoints de comando (171 linhas)
- `backend/api/history.py` — endpoints de histórico (82 linhas)
- `backend/models/interaction.py` — modelo Pydantic (45 linhas)
- `backend/models/response.py` — modelos de resposta (60 linhas)
- `backend/api/router.py` — centralização de routers (31 linhas)

### Arquivos Dependentes
- `backend/svc/hermes_bridge.py` — envio ao Hermes Agent
- `backend/db/repo.py` — persistência de interações (198 linhas)
- `backend/config/settings.py` — configuração do canal
- `backend/api/router.py` — registro de routers

### ADRs Relacionados
- [ADR-002](adrs/adr-002.md) — FastAPI para endpoints REST
- [ADR-002](adrs/adr-002.md) — Pydantic v2 para validação

## Entregáveis
- Endpoints REST completos para comandos e histórico
- Integração completa com Hermes Bridge e banco de dados
- Paginação e busca por texto no histórico
- Testes unitários e de integração
- Cobertura de código >= 80%

## Testes
- [x] Teste de POST /api/command com mensagem válida e resposta 202
- [x] Teste de POST /api/command retornando ID e status "processing"
- [x] Teste de POST /api/command com Hermes indisponível retornando erro
- [x] Teste de GET /api/command/{id} retornando interação criada
- [x] Teste de GET /api/history sem filtros retornando lista paginada
- [x] Teste de GET /api/history com parâmetro search filtrando por texto
- [x] Teste de GET /api/history com limit e offset
- [x] Teste de GET /api/history/{id} retornando interação específica
- [x] Teste de DELETE /api/history limpando todos os registros
- [x] Teste de medição de duração em milissegundos
- [x] Teste de canal "web" sendo gravado corretamente
- [x] Teste de integração com banco de dados

## Critérios de Sucesso
- Todos os testes passando
- Cobertura >= 80%
- Endpoints seguindo a TechSpec (Seção 3.1)
- Integração completa Hermes Bridge + banco de dados
- Paginação e busca funcionando corretamente
