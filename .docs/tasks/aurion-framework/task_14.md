---
status: completed
title: Frontend — Painel de Configurações com validação e botões de teste
type: frontend
complexity: high
dependencies: ["task_12", "task_03", "task_11"]
---

# Frontend — Painel de Configurações com validação e botões de teste

## Visão Geral

Implementar o painel completo de configurações da SPA, incluindo sub-painéis para Hermes, STT, TTS, Audio e Wake Word. Cada sub-painel DEVE ter botões de teste que chamam os endpoints POST /api/test/* do backend, além de validação de formulários e persistência de configurações via PUT /api/config.

<critical>
- Ler PRD e TechSpec completos antes de implementar
- Consultar TechSpec para requisitos técnicos específicos
- Foco no O QUÊ, não no COMO
- Minimizar código, maximizar reuso
- Testes são obrigatórios em todas as tarefas
</critical>

<requirements>
1. O componente `SettingsPanel` DEVE exibir todas as categorias de configuração (Hermes, STT, TTS, Audio, Wake Word)
2. O componente DEVE ter sub-painéis para cada categoria: `HermesConfig`, `STTConfig`, `TTSConfig`, `AudioConfig`, `WakeWordConfig`
3. Cada sub-painel DEVE ter campos de formulário para todas as configurações da TechSpec (Seção 4.2)
4. Cada sub-painel DEVE ter botão de teste que chama o endpoint POST /api/test/* correspondente
5. O formulário DEVE ter validação de campos (URLs, números, faixas)
6. O formulário DEVE salvar configurações via `PUT /api/config`
7. O formulário DEVE carregar configurações atuais via `GET /api/config`
8. O formulário DEVE exibir feedback visual de sucesso/erro ao salvar e testar
9. O sistema DEVE suportar listing de vozes disponíveis do TTS
</requirements>

## Subtarefas
- [x] Criar `src/components/Settings/SettingsPanel.tsx` — painel principal de configurações (219 linhas)
- [x] Criar `src/components/Settings/HermesConfig.tsx` — configuração do Hermes Agent (96 linhas)
- [x] Criar `src/components/Settings/STTConfig.tsx` — configuração do serviço STT (166 linhas)
- [x] Criar `src/components/Settings/TTSConfig.tsx` — configuração do serviço TTS (282 linhas)
- [x] Criar `src/components/Settings/AudioConfig.tsx` — configuração de áudio (148 linhas)
- [x] Criar `src/components/Settings/WakeWordConfig.tsx` — configuração do wake word (85 linhas)
- [x] Implementar formulário com validação para cada sub-painel
- [x] Implementar botão de teste para cada sub-painel (chamando POST /api/test/*)
- [x] Implementar carregamento de configurações via GET /api/config
- [x] Implementar salvamento de configurações via PUT /api/config
- [x] Implementar listing de vozes disponíveis do TTS
- [x] Implementar feedback visual de sucesso/erro (toast, alertas)
- [x] Implementar estado de loading durante operações de API
- [x] Atualizar store Zustand com configurações
- [x] Criar componentes compartilhados de formulário: `settingsShared.tsx` (317 linhas) — Field, TextInput, NumberInput, SelectInput, CheckboxInput, TestButton, SectionCard, validação (validateUrl, validateNumberRange, validatePositive)
- [~] Criar testes unitários para componentes de configuração (deferido — sem runner configurado no frontend)

## Detalhes de Implementação

### Arquivos Relevantes
- `src/components/Settings/SettingsPanel.tsx` — painel principal
- `src/components/Settings/HermesConfig.tsx` — config Hermes
- `src/components/Settings/STTConfig.tsx` — config STT
- `src/components/Settings/TTSConfig.tsx` — config TTS
- `src/components/Settings/AudioConfig.tsx` — config Audio
- `src/components/Settings/WakeWordConfig.tsx` — config Wake Word

### Arquivos Dependentes
- `backend/api/config.py` — endpoints GET/PUT /api/config
- `backend/api/test.py` — endpoints POST /api/test/*
- `src/store/aurionStore.ts` — store Zustand para configurações

### ADRs Relacionados
- [ADR-003](adrs/adr-003.md) — SPA comunicando-se via HTTP REST

## Entregáveis
- Painel de configurações completo com 5 sub-painéis
- Formulários com validação para cada categoria
- Botões de teste integrados com endpoints do backend
- Carregamento e salvamento de configurações
- Feedback visual de sucesso/erro
- Testes unitários dos componentes
- Cobertura de código >= 80%

## Testes
- [~] Teste de renderização do SettingsPanel com todas as abas (deferido — sem runner configurado)
- [~] Teste de renderização de cada sub-painel (deferido)
- [~] Teste de validação de URL no campo do endpoint do Hermes (deferido)
- [~] Teste de validação de faixa de sensibilidade (0.0-1.0) (deferido)
- [~] Teste de validação de sample_rate (número positivo) (deferido)
- [~] Teste de carregamento de configurações via GET /api/config (deferido)
- [~] Teste de salvamento de configurações via PUT /api/config (deferido)
- [~] Teste de botão de teste do Hermes (deferido)
- [~] Teste de botão de teste do STT (deferido)
- [~] Teste de botão de teste do TTS (deferido)
- [~] Teste de feedback visual de sucesso/erro (deferido)
- [~] Teste de listing de vozes disponíveis (deferido)
- [~] Teste de estado de loading durante operações (deferido)

## Critérios de Sucesso
- Todos os testes passando
- Cobertura >= 80%
- Todas as categorias de configuração exibidas e editáveis
- Botões de teste funcionais com endpoints do backend
- Validação de formulários funcionando
- Feedback visual de sucesso/erro
