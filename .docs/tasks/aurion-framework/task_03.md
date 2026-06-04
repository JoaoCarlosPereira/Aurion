---
status: completed
title: Gerenciador de configurações (Config Manager)
type: backend
complexity: medium
dependencies: ["task_01"]
---

# Gerenciador de configurações (Config Manager)

## Visão Geral

Implementar o sistema de gerenciamento de configurações persistentes usando Pydantic Settings e armazenamento em JSON. O Config Manager será responsável por ler, validar, persistir e atualizar todas as configurações do sistema, incluindo Hermes, STT, TTS, wake word e áudio.

<critical>
- Ler PRD e TechSpec completos antes de implementar
- Consultar TechSpec para requisitos técnicos específicos
- Foco no O QUÊ, não no COMO
- Minimizar código, maximizar reuso
- Testes são obrigatórios em todas as tarefas
</critical>

<requirements>
1. O módulo `config/settings.py` DEVE usar pydantic-settings para leitura de variáveis de ambiente e config.json
2. Os modelos `config/models.py` DEVEM definir todas as estruturas de configuração listadas na TechSpec (Seção 3.3)
3. O Config Manager DEVE persistir configurações em `config.json` no diretório do projeto
4. Devem ser suportadas leituras parciais (GET) e atualizações parciais (PUT) de configurações
5. Os modelos DEVEM validar tipos e faixas de valores (ex: sensibilidade 0.0-1.0)
6. O arquivo DEVE suportar valores padrão conforme a TechSpec (Seção 4.2)
7. O sistema DEVE fornecer um método de reset para restaurar configurações padrão
</requirements>

## Subtarefas
- [x] Criar `backend/config/__init__.py` com inicialização do Config Manager
- [x] Criar `backend/config/models.py` com todas as classes de configuração (Pydantic):
  - [x] `HermesConfig` — endpoint, auth_token
  - [x] `STTConfig` — engine, model, language, threads, beam_size, max_context
  - [x] `TTSConfig` — engine, voice, rate, volume, external (com sub-config)
  - [x] `ExternalTTSConfig` — enabled, endpoint, api_key, params, format, timeout
  - [x] `WakeWordConfig` — engine, sensitivity, keyword
  - [x] `AudioConfig` — sample_rate, channels, chunk_size, silence_threshold, wake_word_timeout
  - [x] `AppConfig` — classe raiz com todas as sub-configurações (inclui `database`)
- [x] Implementar leitura de config.json com fallback para valores padrão
- [x] Implementar escrita de config.json com serialização JSON
- [x] Implementar validação de tipos e faixas de valores
- [x] Implementar método de atualização parcial (merge de configurações)
- [x] Implementar método de reset para valores padrão
- [x] Criar métodos GET/PUT na API para /api/config
- [x] Criar testes unitários para validação de configurações
- [x] Criar testes de integração para persistência em config.json

## Detalhes de Implementação

### Arquivos Relevantes
- `backend/config/models.py` — modelos Pydantic de configuração
- `backend/config/settings.py` — Config Manager com leitura/escrita
- `backend/api/config.py` — endpoints REST para configurações

### Arquivos Dependentes
- `backend/api/router.py` — registro dos routers de configuração
- `backend/main.py` — inicialização do Config Manager

### ADRs Relacionados
- [ADR-002](adrs/adr-002.md) — Pydantic v2 para serialização de dados
- [ADR-002](adrs/adr-002.md) — pydantic-settings para configuração

## Entregáveis
- Modelos Pydantic completos para todas as configurações
- Config Manager com leitura, escrita e validação
- Endpoints REST GET/PUT /api/config
- Testes unitários e de integração
- Cobertura de código >= 80%

## Testes
- [x] Teste de leitura de config.json válido com todas as chaves
- [x] Teste de fallback para valores padrão quando config.json não existe
- [x] Teste de validação de faixa de sensibilidade (0.0-1.0)
- [x] Teste de atualização parcial de configurações (merge)
- [x] Teste de reset para configurações padrão
- [x] Teste de serialização e desserialização JSON
- [x] Teste de validação de URL no endpoint do Hermes
- [x] Teste de validação de sample_rate (16000)
- [x] Teste de GET /api/config retornando todas as configurações
- [x] Teste de PUT /api/config atualizando configurações parciais
- [x] Teste de persistência em arquivo config.json

> Observações: o token do Hermes (`hermes.auth_token`) NÃO é exposto no GET
> nem no PUT (omitido da resposta), conforme TechSpec Seção 11. Os testes usam
> `tmp_path` para criar um `config.json` local isolado, sem depender de arquivo
> versionado. A integração final do router e do `ConfigManager` será feita na
> task_18 (este módulo apenas expõe o objeto `router` e a dependência
> `get_config_manager_dep`).

## Critérios de Sucesso
- Todos os testes passando
- Cobertura >= 80%
- Modelos Pydantic com validação completa
- Persistência em config.json funcionando
- Endpoints REST operacionais
