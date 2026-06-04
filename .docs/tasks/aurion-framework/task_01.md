---
status: completed
title: Configuração inicial do projeto
type: backend
complexity: low
dependencies: []
---

# Configuração inicial do projeto

## Visão Geral

Criar a estrutura de diretórios e arquivos de configuração base para o projeto Aurion, estabelecendo os alicerces para o desenvolvimento do backend e frontend. Esta tarefa define a organização do projeto, as dependências iniciais e os arquivos de configuração que todas as demais tarefas irão utilizar.

<critical>
- Ler PRD e TechSpec completos antes de implementar
- Consultar TechSpec para requisitos técnicos específicos
- Foco no O QUÊ, não no COMO
- Minimizar código, maximizar reuso
- Testes são obrigatórios em todas as tarefas
</critical>

<requirements>
1. O projeto DEVE ter a estrutura de diretórios definida na TechSpec (Seção 7 para backend e Seção 6 para frontend)
2. O backend DEVE incluir `requirements.txt` com as dependências listadas na TechSpec (Seção 9)
3. O frontend DEVE incluir `package.json` com as dependências listadas na TechSpec (Seção 9)
4. O projeto DEVE ter um `.gitignore` adequado para Python e JavaScript
5. O projeto DEVE incluir um `config.json.example` com estrutura base de configurações (Seção 4.2 da TechSpec)
6. Devem ser criados arquivos `__init__.py` em todos os pacotes Python do backend
7. O diretório de tarefas existente em `.docs/tasks/aurion-framework/task_files/` DEVE ser preservado e não versionado (excluído do git apenas se necessário)
</requirements>

## Subtarefas
- [x] Criar estrutura de diretórios do backend (`backend/api/`, `backend/svc/`, `backend/db/`, `backend/config/`, `backend/models/`)
- [x] Criar estrutura de diretórios do frontend (`frontend/src/components/`, `frontend/src/hooks/`, `frontend/src/store/`, `frontend/src/services/`, `frontend/src/styles/`)
- [x] Criar `backend/requirements.txt` com todas as dependências listadas na TechSpec (Seção 9)
- [x] Criar `frontend/package.json` com dependências listadas na TechSpec (Seção 9)
- [x] Criar `.gitignore` com padrões Python, Node.js e arquivos locais
- [x] Criar `backend/config.json.example` com estrutura base de configurações (Seção 4.2 da TechSpec)
- [x] Criar arquivos `__init__.py` em todos os módulos do backend
- [x] Criar `backend/main.py` com estrutura mínima do FastAPI (app = FastAPI())
- [x] Criar `frontend/index.html` como ponto de entrada
- [x] Criar `frontend/vite.config.ts` com configuração básica
- [x] Criar `frontend/tsconfig.json` com configuração básica
- [x] Criar `frontend/tailwind.config.ts` com configuração básica
- [x] Verificar se todos os diretórios foram criados corretamente
- [x] Executar `pip install -r backend/requirements.txt` para verificar compatibilidade
- [x] Executar `npm install` no frontend para verificar compatibilidade

## Detalhes de Implementação

### Arquivos Relevantes
- `backend/requirements.txt` — dependências Python do backend
- `frontend/package.json` — dependências do frontend
- `.gitignore` — exclusões de versionamento
- `backend/config.json.example` — exemplo de configuração
- `backend/main.py` — entry point do FastAPI
- `frontend/vite.config.ts` — configuração do Vite
- `frontend/tsconfig.json` — configuração do TypeScript

### Arquivos Dependentes
- Nenhum — esta tarefa é independente

### ADRs Relacionados
- [ADR-001](adrs/adr-001.md) — Arquitetura Servidor Local + Web App
- [ADR-002](adrs/adr-002.md) — Stack de Backend Python com FastAPI
- [ADR-003](adrs/adr-003.md) — Arquitetura SPA Separada + FastAPI Backend

## Entregáveis
- Estrutura completa de diretórios backend/ e frontend/
- requirements.txt com todas as dependências listadas na TechSpec (Seção 9)
- package.json com todas as dependências listadas na TechSpec (Seção 9)
- .gitignore adequado
- config.json.example com estrutura completa
- main.py com FastAPI app inicializado
- vite.config.ts, tsconfig.json, tailwind.config.ts configurados
- Testes unitários para validação da estrutura

## Testes
- [x] Verificar que `pip install -r backend/requirements.txt` não gera erros de compatibilidade — dry-run passou com 17 pacotes prontos
- [x] Verificar que `npm install` no frontend não gera erros — dry-run passou com 110 pacotes
- [x] Verificar que `python -c "import fastapi"` não gera erro de importação — FastAPI 0.115.0 importado com sucesso
- [x] Verificar que `npx vite --version` é executado com sucesso — vite/8.0.16 detectado
- [x] Verificar que todos os arquivos __init__.py existem nos módulos Python — todos presentes (api, config, db, models, svc)
- [x] Verificar que config.json.example tem todas as chaves da TechSpec (Seção 4.2) — hermes, stt, tts, wake_word, audio confirmadas

## Critérios de Sucesso
- Todos os testes passando
- Estrutura de diretórios idêntica à descrita na TechSpec (Seções 6 e 7)
- Nenhuma dependência com erro de instalação
- Arquivos de configuração com estrutura completa
