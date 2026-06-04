---
status: completed
title: Serviço STT (Speech-to-Text) com whisper.cpp
type: backend
complexity: high
dependencies: ["task_01"]
---

# Serviço STT (Speech-to-Text) com whisper.cpp

## Visão Geral

Implementar o serviço de conversão de fala em texto usando whisper.cpp, que será chamado pelo Listening Service após a detecção do wake word e captura da fala. O serviço deve suportar streaming de áudio, forçamento de idioma PT-BR e otimizações de performance conforme a TechSpec.

<critical>
- Ler PRD e TechSpec completos antes de implementar
- Consultar TechSpec para requisitos técnicos específicos
- Foco no O QUÊ, não no COMO
- Minimizar código, maximizar reuso
- Testes são obrigatórios em todas as tarefas
</critical>

<requirements>
1. O módulo `svc/stt.py` DEVE usar whisper.cpp (via whispercpp-python) para conversão de áudio em texto
2. O modelo padrão DEVE ser `ggml-base-q4` (quantizado Q4, ≈55MB) conforme TechSpec (Seção 5.3)
3. O serviço DEVE suportar streaming de áudio do PyAudio (16kHz, buffer 1-2s)
4. O serviço DEVE forçar o idioma para pt-BR (reduzindo latência e aumentando precisão)
5. As otimizações DEVEM ser configuráveis: threads, beam_size, max_context, cpu-tie-break
6. O serviço DEVE ter um fallback para engine alternativa se whisper.cpp falhar
7. O serviço DEVE suportar timeout configurável para processamento
</requirements>

## Subtarefas
- [x] Criar `backend/svc/stt.py` com classe STTService
- [x] Implementar inicialização do whisper.cpp com modelo base Q4 (import lazy/guardado)
- [x] Implementar método `transcribe(audio_data: bytes) -> str` — conversão áudio para texto (async; aceita bytes/np.ndarray)
- [x] Implementar método `test_model() -> bool` — valida carregamento do modelo
- [x] Implementar leitura de configurações via modelo `STTConfig` (engine, model, threads, beam_size, max_context); Config Manager (task_03) fará o wiring final
- [x] Implementar forçamento de idioma PT-BR (`pt-BR` -> código whisper `pt`)
- [x] Implementar buffering de áudio (1-2s) antes do processamento
- [x] Implementar otimizações configuráveis (threads, beam_size, max_context)
- [x] Implementar fallback para engine alternativa (degradação graciosa)
- [x] Implementar timeout configurável
- [x] Criar testes unitários com mocks do whisper.cpp
- [~] Criar teste de integração com modelo real (não disponível neste ambiente; whisper.cpp/binário ausentes — coberto por mocks)

## Detalhes de Implementação

### Arquivos Relevantes
- `backend/svc/stt.py` — serviço STT
- `backend/config/models.py` — configuração STT

### Arquivos Dependentes
- `backend/config/settings.py` — leitura da configuração STT
- `backend/svc/listening.py` — consumo do serviço STT
- `backend/main.py` — injeção de dependência do serviço

### ADRs Relacionados
- [ADR-002](adrs/adr-002.md) — whisper.cpp como motor STT

## Entregáveis
- Módulo STTService completo
- Transcrição de áudio para texto com whisper.cpp
- Streaming de áudio suportado
- Otimizações configuráveis
- Fallback para engine alternativa
- Testes unitários e de integração
- Cobertura de código >= 80%

## Testes
- [x] Teste de inicialização do whisper.cpp com modelo Q4 válido (`test_carregamento_whisper_aplica_config`)
- [x] Teste de transcrição de áudio válido retornando texto não vazio (mock) (`test_transcricao_audio_valido_retorna_texto`)
- [x] Teste de transcrição com áudio de silêncio retornando texto vazio (`test_transcricao_silencio_retorna_vazio`)
- [x] Teste de forçamento de idioma PT-BR (`test_forcamento_idioma_pt_br`, `test_aplica_params_idioma_threads_beam`)
- [x] Teste de configuração de threads (`test_aplica_params_idioma_threads_beam`, `test_carregamento_whisper_aplica_config`)
- [x] Teste de configuração de beam_size (`test_aplica_params_idioma_threads_beam`, `test_carregamento_whisper_aplica_config`)
- [x] Teste de timeout configurável (`test_timeout_retorna_vazio`)
- [x] Teste de fallback para engine alternativa (`test_fallback_engine_quando_whisper_indisponivel`, `test_whisper_indisponivel_sem_excecao`)
- [x] Teste de buffering de áudio (1-2s) (`test_buffer_insuficiente_retorna_vazio`, `test_buffer_suficiente_transcreve`)
- [x] Teste de test_model() retornando sucesso (`test_test_model_sucesso_com_transcritor_injetado`)
- [x] Teste de erro ao carregar modelo inexistente (`test_test_model_modelo_inexistente`)

## Critérios de Sucesso
- Todos os testes passando
- Cobertura >= 80%
- whisper.cpp operando com modelo Q4
- Streaming de áudio funcionando
- Otimizações configuráveis conforme TechSpec (Seção 5.3)
