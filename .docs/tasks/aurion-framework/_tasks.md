# Aurion Framework — Lista de Tarefas

## Tarefas

| # | Título | Status | Complexidade | Dependências |
|---|--------|--------|--------------|--------------|
| 01 | Configuração inicial do projeto | completed | low | — |
| 02 | Camada de persistência — SQLite com aiosqlite | completed | medium | task_01 |
| 03 | Gerenciador de configurações (Config Manager) | completed | medium | task_01 |
| 04 | Hermes Bridge — Cliente HTTP para Hermes Agent | completed | medium | task_03 |
| 05 | API REST de comandos e histórico | completed | high | task_02, task_03, task_04 |
| 06 | Engine de detecção de Wake Word (Porcupine) | completed | medium | task_01 |
| 07 | Serviço STT (Speech-to-Text) com whisper.cpp | completed | high | task_01 |
| 08 | Serviço TTS (Text-to-Speech) com edge-tts e streaming externo | completed | medium | task_01 |
| 09 | Listening Service — Loop principal de escuta | completed | high | task_06, task_07, task_08 |
| 10 | Servidor WebSocket — Status em tempo real e streaming de áudio | completed | high | task_09, task_05 |
| 11 | API REST completa — Endpoints de teste e configurações avançadas | completed | medium | task_05 |
| 12 | Frontend — Setup do projeto Vite + React + TypeScript | completed | low | — |
| 13 | Frontend — Componente de Chat com integração API e WebSocket | completed | high | task_12, task_05, task_10 |
| 14 | Frontend — Painel de Configurações com validação e botões de teste | completed | high | task_12, task_03, task_11 |
| 15 | Frontend — Painel de Histórico com busca e paginação | completed | medium | task_12, task_05 |
| 16 | Frontend — Microfone Web com gravação via WebSocket | completed | high | task_12, task_10 |
| 17 | Frontend — Player de áudio TTS no navegador | completed | medium | task_12, task_08 |
| 18 | Integração final, testes E2E e ajustes de latência | completed | critical | task_13, task_14, task_15, task_16, task_17 |
