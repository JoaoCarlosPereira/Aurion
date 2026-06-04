---
status: completed
title: Camada de persistência — Banco de dados SQLite com aiosqlite
type: backend
complexity: medium
dependencies: ["task_01"]
---

# Camada de persistência — Banco de dados SQLite com aiosqlite

## Visão Geral

Implementar a camada de persistência do sistema usando SQLite com aiosqlite, incluindo a criação do esquema de banco de dados com a tabela `interactions`, migrations iniciais, e funções CRUD completas seguindo o repository pattern. Esta camada será a base para todas as operações de armazenamento de histórico de interações.

<critical>
- Ler PRD e TechSpec completos antes de implementar
- Consultar TechSpec para requisitos técnicos específicos
- Foco no O QUÊ, não no COMO
- Minimizar código, maximizar reuso
- Testes são obrigatórios em todas as tarefas
</critical>

<requirements>
1. O módulo `db/database.py` DEVE criar e gerenciar a conexão com o banco SQLite usando aiosqlite
2. A tabela `interactions` DEVE ser criada automaticamente na inicialização, seguindo o esquema da TechSpec (Seção 4.1)
3. Devem ser implementadas operações CRUD completas: CREATE, READ, UPDATE, DELETE para interações
4. O módulo `db/models.py` DEVE definir os modelos Pydantic para interação
5. O módulo `db/repo.py` DEVE implementar o repository pattern com métodos assíncronos
6. Os índices `idx_interactions_timestamp`, `idx_interactions_channel`, e `idx_interactions_status` DEVEM ser criados
7. A persistência DEVE ser totalmente assíncrona (aiosqlite)
8. O arquivo `config.json` DEVE apontar para o caminho do banco de dados
</requirements>

## Subtarefas
- [x] Criar `backend/db/__init__.py` com inicialização do banco
- [x] Criar `backend/db/database.py` com classe de conexão aiosqlite assíncrona
- [x] Implementar criação da tabela `interactions` com todas as colunas da TechSpec (Seção 4.1)
- [x] Implementar criação dos 3 índices obrigatórios
- [x] Criar `backend/db/models.py` com modelo Pydantic para Interaction
- [x] Criar `backend/db/repo.py` com repository pattern (async methods)
- [x] Implementar método `create_interaction()` — INSERT com UUID
- [x] Implementar método `get_interaction_by_id()` — SELECT por ID
- [x] Implementar método `list_interactions()` — SELECT com LIMIT, OFFSET e busca por texto
- [x] Implementar método `delete_all_interactions()` — DELETE todos os registros
- [x] Implementar método `get_interactions_by_channel()` — filtro por canal
- [x] Implementar método `get_interactions_by_status()` — filtro por status
- [x] Implementar método `get_recent_interactions()` — ordenado por timestamp DESC
- [x] Implementar conexão singleton com gerenciamento de ciclo de vida (iniciar/fechar)
- [x] Criar testes unitários para todas as operações CRUD
- [x] Criar teste de integração verificando persistência real no SQLite

> Nota: além das operações enumeradas, foi adicionado `update_interaction()` para cumprir o requisito 3 (CRUD completo inclui UPDATE) — necessário ao fluxo `POST /api/command` (registro inicial `processing` posteriormente completado).

## Detalhes de Implementação

### Arquivos Relevantes
- `backend/db/database.py` — conexão e inicialização do banco
- `backend/db/models.py` — modelos Pydantic
- `backend/db/repo.py` — repository pattern
- `backend/config/settings.py` — configuração do caminho do banco (dependência futura)

### Arquivos Dependentes
- `backend/config/settings.py` — leitura do caminho do banco de dados
- `backend/api/history.py` — consumo do repository para endpoints

### ADRs Relacionados
- [ADR-002](adrs/adr-002.md) — Python com aiosqlite para SQLite assíncrono

## Entregáveis
- Módulo db completo com database.py, models.py e repo.py
- Tabelas e índices criados automaticamente
- Operações CRUD assíncronas completas
- Testes unitários e de integração
- Cobertura de código >= 80%

## Testes
- [x] Teste de criação de interação com dados válidos e verificação do INSERT
- [x] Teste de busca por ID e verificação de retorno correto
- [x] Teste de busca paginada com LIMIT e OFFSET
- [x] Teste de busca com filtro por texto (LIKE)
- [x] Teste de busca por canal ('local' ou 'web')
- [x] Teste de busca por status ('success', 'error', 'timeout')
- [x] Teste de deleção de todos os registros
- [x] Teste de ordem decrescente por timestamp
- [x] Teste de constraints CHECK (channel e status)
- [x] Teste de criação automática da tabela ao iniciar conexão

## Critérios de Sucesso
- Todos os testes passando
- Cobertura >= 80%
- Schema idêntico ao definido na TechSpec (Seção 4.1)
- Todas as operações assíncronas funcionando corretamente
- Índices criados e verificáveis via PRAGMA
