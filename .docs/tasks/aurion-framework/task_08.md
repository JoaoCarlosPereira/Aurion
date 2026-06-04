---
status: completed
title: Serviço TTS (Text-to-Speech) com edge-tts e streaming externo
type: backend
complexity: medium
dependencies: ["task_01"]
---

# Serviço TTS (Text-to-Speech) com edge-tts e streaming externo

## Visão Geral

Implementar o serviço de síntese de voz usando edge-tts como engine padrão e suporte a TTS externo em streaming. O serviço DEVE suportar recebimento e buffer de streaming do TTS externo, com áudio recebido em chunks progressivos via Transfer-Encoding: chunked, sem esperar o arquivo completo terminar.

<critical>
- Ler PRD e TechSpec completos antes de implementar
- Consultar TechSpec para requisitos técnicos específicos
- Foco no O QUÊ, não no COMO
- Minimizar código, maximizar reuso
- Testes são obrigatórios em todas as tarefas
</critical>

<requirements>
1. O módulo `svc/tts.py` DEVE usar edge-tts como engine padrão
2. O serviço DEVE suportar TTS externo com streaming de áudio via Transfer-Encoding: chunked
3. **CRÍTICO**: O serviço DEVE receber áudio em chunks progressivos via HTTP chunked streaming e não esperar o arquivo completo terminar
4. O serviço DEVE expor um método assíncrono `synthesize(text: str) -> AsyncGenerator[bytes, None]` para streaming
5. O serviço DEVE ter um buffer de playback configurável (`stream_buffer_ms`, padrão 500ms)
6. A voz padrão DEVE ser `pt-BR-FabioNeural` conforme TechSpec (Seção 5.4)
7. O serviço DEVE suportar fallback automático para edge-tts se TTS externo falhar
8. O serviço DEVE suportar parâmetros configuráveis: rate, volume, voice
9. O serviço DEVE suportar headers customizados para o TTS externo (ex: Authorization)
10. O serviço DEVE suportar formatos configuráveis (mp3 padrão)
</requirements>

## Subtarefas
- [x] Criar `backend/svc/tts.py` com classe TTSService
- [x] Implementar método `synthesize(text: str) -> AsyncGenerator[bytes, None]` — streaming de áudio
- [x] Implementar geração de áudio com edge-tts (engine padrão)
- [x] Implementar chamada HTTP chunked para TTS externo com stream assíncrono
- [x] Implementar buffer de playback configurável (stream_buffer_ms)
- [x] Implementar buffer circular para acumulação de chunks
- [x] Implementar reprodução progressiva assim que primeiros chunks chegarem
- [x] Implementar fallback automático para edge-tts
- [x] Implementar suporte a headers customizados
- [x] Implementar configuração de voz, rate e volume
- [x] Implementar método `test_connection() -> bool` para teste do TTS
- [x] Implementar método `list_voices() -> list[str]` para listar vozes disponíveis
- [x] Criar testes unitários com mocks do edge-tts e httpx
- [x] Criar teste de streaming chunked simulado

## Detalhes de Implementação

### Arquivos Relevantes
- `backend/svc/tts.py` — serviço TTS
- `backend/config/models.py` — configuração TTS

### Arquivos Dependentes
- `backend/config/settings.py` — leitura da configuração TTS
- `backend/svc/listening.py` — consumo do serviço TTS
- `backend/api/test.py` — endpoint de teste de conexão TTS

### ADRs Relacionados
- [ADR-002](adrs/adr-002.md) — edge-tts como motor TTS

## Entregáveis
- Módulo TTSService completo com edge-tts e TTS externo streaming
- Streaming assíncrono de áudio (AsyncGenerator)
- Buffer de playback configurável
- Fallback automático para edge-tts
- Testes unitários e de integração
- Cobertura de código >= 80%

## Testes
- [x] Teste de sintetização com edge-tts retornando áudio válido
- [x] Teste de streaming chunked do TTS externo (simulado com mock)
- [x] Teste de buffer de playback configurável
- [x] Teste de buffer circular acumulando chunks progressivamente
- [x] Teste de reprodução progressiva iniciando antes do stream terminar
- [x] Teste de fallback automático para edge-tts quando TTS externo falha
- [x] Teste de headers customizados sendo enviados ao TTS externo
- [x] Teste de configuração de voz (pt-BR-FabioNeural)
- [x] Teste de configuração de rate e volume
- [x] Teste de test_connection() retornando sucesso com edge-tts
- [x] Teste de test_connection() retornando sucesso com TTS externo
- [x] Teste de list_voices() retornando vozes PT-BR

## Critérios de Sucesso
- Todos os testes passando
- Cobertura >= 80%
- Streaming chunked funcionando corretamente
- Buffer de playback configurável
- Fallback automático funcionando
- Voz padrão pt-BR configurável
