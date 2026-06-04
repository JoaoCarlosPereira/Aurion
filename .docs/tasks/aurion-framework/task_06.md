---
status: completed
title: Engine de detecção de Wake Word (Porcupine)
type: backend
complexity: medium
dependencies: ["task_01"]
---

# Engine de detecção de Wake Word (Porcupine)

## Visão Geral

Implementar o motor de detecção da palavra "Aurion" usando Porcupine (Picovoice), que opera continuamente no stream de áudio capturado pelo PyAudio. O engine deve ser configurável em sensibilidade e suportar o modelo .ppn treinado para a pronúncia brasileira.

<critical>
- Ler PRD e TechSpec completos antes de implementar
- Consultar TechSpec para requisitos técnicos específicos
- Foco no O QUÊ, não no COMO
- Minimizar código, maximizar reuso
- Testes são obrigatórios em todas as tarefas
</critical>

<requirements>
1. O módulo `svc/wakeword.py` DEVE usar a biblioteca Porcupine para detecção da palavra "Aurion"
2. O wake word engine DEVE ser configurável via Config Manager (engine, sensitivity, keyword)
3. A sensibilidade DEVE ser validada no intervalo 0.0 a 1.0 (padrão 0.5)
4. O motor DEVE suportar o arquivo de modelo .ppn para a palavra "Aurion" em português brasileiro
5. O motor DEVE processar áudio em 16kHz, 1 canal (conforme configuração de áudio)
6. O motor DEVE retornar um boolean indicando detecção ou o resultado da análise
7. O motor DEVE ter um timeout configurável (padrão 10s) para voltar ao modo escuta
8. O motor DEVE ser eficiente o suficiente para operação em tempo real (conforme TechSpec Seção 5.2)
</requirements>

## Subtarefas
- [x] Criar `backend/svc/wakeword.py` com classe WakeWordEngine
- [x] Implementar inicialização do Porcupine com modelo .ppn
- [x] Implementar método `process(audio_frame: bytes) -> bool` — detecta wake word
- [x] Implementar método `test_model() -> bool` — valida carregamento do modelo
- [x] Implementar leitura de sensibilidade do Config Manager
- [x] Implementar validação de faixa de sensibilidade (0.0-1.0)
- [x] Implementar gerenciamento de ciclo de vida (iniciar/parar)
- [x] Implementar timeout configurável para modo escuta
- [x] Implementar fallback para modelo padrão se .ppn personalizado não existir
- [x] Criar testes unitários com mocks do Porcupine
- [x] Criar teste de carregamento de modelo

## Detalhes de Implementação

### Arquivos Relevantes
- `backend/svc/wakeword.py` — engine de detecção de wake word
- `backend/config/models.py` — configuração do wake word

### Arquivos Dependentes
- `backend/config/settings.py` — leitura da configuração de wake word
- `backend/svc/listening.py` — consumo do wake word engine

### ADRs Relacionados
- [ADR-002](adrs/adr-002.md) — Porcupine para detecção de wake word local

## Entregáveis
- Módulo WakeWordEngine completo
- Detecção de "Aurion" em stream de áudio
- Configuração de sensibilidade via Config Manager
- Testes unitários e de integração
- Cobertura de código >= 80%

## Testes
- [x] Teste de inicialização do Porcupine com modelo válido
- [x] Teste de processamento de frame de áudio sem detecção
- [x] Teste de processamento de frame de áudio com detecção (mock)
- [x] Teste de validação de sensibilidade fora da faixa (0.0 e 1.0 extremos)
- [x] Teste de timeout configurável
- [x] Teste de fallback para modelo padrão
- [x] Teste de gerenciamento de ciclo de vida (iniciar/parar)
- [x] Teste de sensibilidade padrão (0.5)

## Notas de Implementação

- `backend/svc/wakeword.py` implementa `WakeWordEngine` com import lazy de
  `pvporcupine` via `_load_pvporcupine()`. Quando a biblioteca está indisponível
  (ou falha ao criar o handle), o engine degrada graciosamente para modo no-op:
  loga o problema e nunca detecta (TechSpec Seção 10).
- Interface assíncrona via `process_async()` (executa o `process` síncrono em
  thread pool com `asyncio.to_thread`) e callback opcional `on_detected` disparado
  ao detectar "Aurion".
- `WakeWordConfig` (Pydantic v2) define e valida `sensitivity` em [0.0, 1.0]
  (padrão 0.5), `keyword`, `keyword_path` (.ppn) e `wake_word_timeout` (padrão 10s).
  Mantida local ao módulo para não acoplar ao Config Manager (outra tarefa).
- Fallback: se o `.ppn` personalizado não existir, usa keyword embutida do Porcupine.
- Testes (`backend/tests/test_wakeword.py`) usam mock/monkeypatch do `pvporcupine`,
  sem hardware/binários/rede. 27 testes passando; cobertura de `svc/wakeword.py`: 93%.

## Critérios de Sucesso
- Todos os testes passando
- Cobertura >= 80%
- Detecção funcionando com modelo .ppn
- Sensibilidade configurável e validada
- Operações em 16kHz, 1 canal
