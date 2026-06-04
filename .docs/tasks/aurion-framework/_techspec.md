# TechSpec — Aurion Framework de Assistente Pessoal por Voz

## 1. Resumo Executivo

Implementação de um framework de assistente pessoal por voz que opera localmente no computador do usuário, detectando a palavra "Aurion" no áudio do microfone, enviando comandos ao Hermes Agent via HTTP REST e retornando respostas por voz (TTS) e texto. A arquitetura consiste em um backend Python/FastAPI com SPA React/TypeScript separada, comunicando-se via REST e WebSocket.

**Trade-off principal**: SPA separada oferece melhor experiência do usuário e separação de responsabilidades, mas adiciona complexidade de build e deployment (dois projetos para gerenciar). A opção de servir a SPA construída pelo próprio FastAPI em produção mitiga esse custo.

## 2. Visão Geral do Sistema

### 2.1 Componentes Principais

| Componente | Responsabilidade | Localização |
|------------|-----------------|-------------|
| **Aurion Backend (FastAPI)** | API REST, WebSocket, gerenciamento de serviços de áudio, configuração, histórico | `backend/` |
| **Aurion SPA (React/TS)** | Interface web responsiva, chat, controle de microfone do navegador, painel de configurações | `frontend/` |
| **Servidor de Escuta (Listening Service)** | Loop contínuo de captura de áudio, wake word detection, STT | `backend/svc/listening.py` |
| **Hermes Bridge** | Comunicação HTTP REST com o Hermes Agent | `backend/svc/hermes_bridge.py` |
| **TTS Service** | Síntese de voz e roteamento da resposta | `backend/svc/tts.py` |
| **STT Service** | Speech-to-Text com whisper.cpp (modelo base Q4/Q5) | `backend/svc/stt.py` |
| **Wake Word Engine** | Detecção contínua de "Aurion" no stream de áudio | `backend/svc/wakeword.py` |
| **Database Repository** | Persistência de histórico de interações via aiosqlite | `backend/db/` |
| **Config Manager** | Leitura/escrita de configurações persistentes | `backend/config/` |

### 2.2 Diagrama de Componentes

```
┌─────────────────────────────────────────────────────────────────┐
│                        USUÁRIO                                 │
│  ┌─────────────────────┐    ┌──────────────────────────────┐   │
│  │ Dispositivo Local   │    │ Dispositivo Remoto (Web)     │   │
│  │ (microfone + falantes)│   │ (navegador qualquer dispositivo)│ │
│  └─────────┬───────────┘    └───────────┬──────────────────┘   │
└────────────┼────────────────────────────┼──────────────────────┘
             │                            │
             │ PyAudio                    │ HTTP REST / WebSocket
             │                            │
┌────────────┼────────────────────────────┼──────────────────────┐
│            ▼            AURION BACKEND (Python/FastAPI)        │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  API REST (FastAPI)                                     │  │
│  │  - /api/config           - GET/PUT configurações         │  │
│  │  - /api/history          - GET histórico                 │  │
│  │  - /api/command          - POST envio de comando         │  │
│  │  - /api/test/*           - POST testes de conexão        │  │
│  └──────────────────────────┬──────────────────────────────┘  │
│  ┌──────────────────────────┴──────────────────────────────┐  │
│  │  WebSocket Server                                       │  │
│  │  - /ws/status            - Estado do sistema             │  │
│  │  - /ws/audio             - Streaming TTS para browser    │  │
│  │  - /ws/voice-command     - Comandos por voz (web)        │  │
│  └──────────────────────────┬──────────────────────────────┘  │
│  ┌──────────────────────────┴──────────────────────────────┐  │
│  │  Listening Service (thread dedicada)                    │  │
│  │  PyAudio → Wake Word → STT → Hermes Bridge → TTS       │  │
│  └─────────────────────────────────────────────────────────┘  │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  Database (aiosqlite)                                   │  │
│  └─────────────────────────────────────────────────────────┘  │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  Config Manager (JSON + pydantic-settings)              │  │
│  └─────────────────────────────────────────────────────────┘  │
└──────────────────────────┬─────────────────────────────────────┘
                           │ HTTP REST POST
                           ▼
              ┌─────────────────────────┐
              │  HERMES AGENT           │
              │  (endpoint configurável) │
              └─────────────────────────┘
```

## 3. Design da API

### 3.1 Endpoints REST

#### Configurações

```
GET    /api/config            → Retorna todas as configurações
PUT    /api/config            → Atualiza configurações (parcial ou total)
POST   /api/test/hermes       → Testa conexão com Hermes Agent
POST   /api/test/stt          → Testa conexão com serviço STT
POST   /api/test/tts          → Testa conexão com TTS (edge-tts ou externo, conforme config)
```

#### Histórico

```
GET    /api/history?limit=50&offset=0&search=termo
       → Lista interações paginadas com busca opcional por texto
GET    /api/history/{id}      → Retorna interação específica
DELETE /api/history           → Limpa todo o histórico
```

#### Comandos

```
POST   /api/command
       → Envia comando por texto ao Hermes
       → Body: { "message": "comando do usuário" }
       → Response: { "id": "...", "status": "processing" }
GET    /api/command/{id}      → Consulta status/resposta do comando
```

### 3.2 WebSocket

| Endpoint | Direção | Payload |
|----------|---------|---------|
| `/ws/status` | Server → Client | `{"state": "listening\|detecting\|stt\|processing\|tts\|error", "message": "..."}` |
| `/ws/audio/{session_id}` | Server → Client | `{"type": "audio_chunk", "data": "base64..."}` |
| `/ws/voice-command/{session_id}` | Client → Server | `{"type": "audio_start"}` / `{"type": "audio_chunk", "data": "base64..."}` / `{"type": "audio_end"}` |

### 3.3 Modelo de Dados (Pydantic)

```python
class Interaction(BaseModel):
    id: str
    timestamp: datetime
    channel: Literal["local", "web"]
    input_text: str
    output_text: str | None
    output_audio_url: str | None
    duration_ms: int | None
    status: Literal["success", "error", "timeout"]
    error_message: str | None

class AppConfig(BaseModel):
    hermes: HermesConfig = HermesConfig()
    stt: STTConfig = STTConfig()
    tts: TTSConfig = TTSConfig()
    wake_word: WakeWordConfig = WakeWordConfig()
    audio: AudioConfig = AudioConfig()
```

## 4. Modelos de Dados

### 4.1 Esquema SQLite

```sql
CREATE TABLE IF NOT EXISTS interactions (
    id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    channel TEXT NOT NULL CHECK(channel IN ('local', 'web')),
    input_text TEXT NOT NULL,
    output_text TEXT,
    output_audio_url TEXT,
    duration_ms INTEGER,
    status TEXT NOT NULL CHECK(status IN ('success', 'error', 'timeout')),
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_interactions_timestamp ON interactions(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_interactions_channel ON interactions(channel);
CREATE INDEX IF NOT EXISTS idx_interactions_status ON interactions(status);
```

### 4.2 Arquivo de Configuração

Persistido como `config.json` no diretório do projeto:

```json
{
  "hermes": {
    "endpoint": "http://localhost:8080",
    "auth_token": "secret"
  },
  "stt": {
    "engine": "whisper.cpp",
    "model": "ggml-base-q4",
    "language": "pt-BR",
    "threads": 2,
    "beam_size": 1,
    "max_context": -1
  },
  "tts": {
    "engine": "edge-tts",
    "voice": "pt-BR-FabioNeural",
    "rate": 0,
    "volume": 100,
    "external": {
      "enabled": false,
      "endpoint": "https://api.tts-provider.com/v1/synthesize",
      "api_key": "",
      "params": {
        "input": "",
        "voice": "",
        "speed": 1.0
      },
      "format": "mp3",
      "timeout": 10
    }
  },
  "wake_word": {
    "engine": "porcupine",
    "sensitivity": 0.5,
    "keyword": "aurion"
  },
  "audio": {
    "sample_rate": 16000,
    "channels": 1,
    "chunk_size": 1024,
    "silence_threshold": 300,
    "wake_word_timeout": 10
  }
}
```

## 5. Serviços de Áudio

### 5.1 Listening Service

Serviço que roda em thread dedicada, operando em loop contínuo:

```
[Loop Principal]
    │
    ▼
[Captura áudio com PyAudio] ──▶ Stream de áudio (16kHz, 1 canal)
    │
    ▼
[Wake Word Detection] ──▶ Porcupine/Vosk verifica "Aurion"
    │
    ▼ (detectado)
[Aviso WebSocket: state=detecting]
    │
    ▼
[Captura fala até silêncio] ──▶ VAD detecta 1-3s de silêncio
    │
    ▼
[STT] ──▶ Vosk/speechrecognition converte áudio → texto
    │
    ▼
[Aviso WebSocket: state=processing]
    │
    ▼
[Hermes Bridge] ──▶ POST /api/completion ao Hermes Agent
    │
    ▼
[TTS] ──▶ edge-tts converte resposta → áudio
    │
    ▼
[Roteamento da resposta] ──▶ Local: toca no speaker / Web: envia via WebSocket
    │
    ▼
[Salva no banco] ──▶ INSERT INTO interactions
    │
    ▼
[Reinicia loop]
```

### 5.2 Wake Word Engine

- **Engine**: Porcupine (Picovoice) — leve, rápido, ideal para detecção local
- **Modelo**: Arquivo `.ppn` gerado com a pronúncia "Au-ri-on" em português brasileiro, treinado com vozes masculinas e femininas brasileiras
- **Sensibilidade**: Configurável via interface (0.0 a 1.0), valor padrão 0.5 para português
- **Timeout**: Se não houver fala após detecção, volta ao modo escuta (configurável, padrão 10s)

### 5.3 STT Service

- **Engine**: whisper.cpp (compilação C otimizada, chamada via Python)
- **Modelo**: `ggml-base.pt` (modelo nativo PT-BR) quantizado Q4 (≈55MB) — treinado especificamente com corpus brasileiro, otimizado para sotaques e fonética do português brasileiro. Q5 como alternativa se CPU permitir
- **Stream de áudio**: PyAudio captura a 16kHz, buffer de 1-2s enviado ao whisper.cpp
- **Forçamento de idioma**: `--language pt` (força whisper a reconhecer apenas PT-BR, reduzindo latência e aumentando precisão)
- **Performance esperada**: <2s para 10s de áudio em CPU moderna com AVX2; <4s em hardware básico
- **Otimizações**: `--threads 2` ou `--cpu-tie-break 1` para PCs com poucos núcleos; `--beam-size 1` para latência mínima; `--max-len 1` para evitar geração excessiva de texto

### 5.4 TTS Service

- **Engine padrão**: edge-tts — gratuito, voices naturais da Microsoft Edge, **nativo em PT-BR**
- **Voz padrão**: `pt-BR-FabioNeural` — voz masculina brasileira mais natural
- **Vozes disponíveis PT-BR**: `pt-BR-FabioNeural` (M), `pt-BR-FranciscaNeural` (F), `pt-BR-AntonioNeural` (M)
- **TTS Externo (opcional)**: API configurável via endpoint HTTP POST com **streaming de áudio**
  - **Fluxo**: Recebe texto → POST para endpoint configurável com parâmetros `input`, `voice` e `speed` → **Recebe áudio em stream contínuo (chunked transfer) → Reproduz progressivamente à medida que os chunks chegam**
  - **Streaming**: O endpoint externo deve retornar `Content-Type: audio/mpeg` (ou formato configurável) com `Transfer-Encoding: chunked`, enviando o áudio em blocos progressivamente conforme é sintetizado
  - **Reprodução progressiva**: O backend não espera o stream terminar — começa a reproduzir (local ou via WebSocket) assim que os primeiros chunks de áudio são recebidos, reduzindo drasticamente a latência percebida
  - **Buffer de playback**: Buffer circular configurável para acumular chunks e garantir reprodução suave mesmo com variação na taxa de chegada dos dados
  - **Parâmetros de request**:
    - `input`: texto a ser sintetizado
    - `voice`: identificador da voz (ex: `br-Fabio`, `br-Francisca`)
    - `speed`: velocidade de fala (float, padrão 1.0, ex: 0.8 a 1.5)
  - **Configuração**: `endpoint`, `api_key`, `params` (input/voice/speed), `format` (padrão: mp3), `timeout`, `stream_buffer_ms` (tamanho do buffer de pré-carregamento, padrão: 500ms)
  - **Fallback**: Se `external.enabled` é `false`, endpoint retorna erro ou o streaming falha, usa edge-tts automaticamente
  - **Headers customizados**: Suporte a headers adicionais via config (ex: `Authorization: Bearer <key>`)>`)
- **Configuração de fala**: `rate`, `volume`, `pitch` configuráveis via interface (aplica ao edge-tts)

## 6. Frontend — SPA

### 6.1 Estrutura de Arquivos

```
frontend/
├── public/
│   └── assets/
├── src/
│   ├── components/
│   │   ├── Chat/              # Área de chat principal
│   │   │   ├── ChatMessage.tsx
│   │   │   ├── ChatInput.tsx
│   │   │   └── ChatPanel.tsx
│   │   ├── Settings/          # Painel de configurações
│   │   │   ├── SettingsPanel.tsx
│   │   │   ├── HermesConfig.tsx
│   │   │   ├── STTConfig.tsx
│   │   │   ├── TTSConfig.tsx
│   │   │   └── AudioConfig.tsx
│   │   ├── History/           # Histórico de interações
│   │   │   ├── HistoryPanel.tsx
│   │   │   └── HistorySearch.tsx
│   │   ├── Status/            # Indicadores de estado
│   │   │   ├── SystemStatus.tsx
│   │   │   └── StatusIndicator.tsx
│   │   ├── MicButton/         # Botão de microfone na web
│   │   │   └── MicButton.tsx
│   │   └── AudioPlayer/       # Reprodução de TTS
│   │       └── AudioPlayer.tsx
│   ├── hooks/
│   │   ├── useWebSocket.ts
│   │   ├── useAudioRecorder.ts
│   │   ├── useAurionAPI.ts
│   │   └── useSystemState.ts
│   ├── store/
│   │   └── aurionStore.ts     # Zustand
│   ├── services/
│   │   ├── api.ts             # Axios/fetch wrapper
│   │   └── websocket.ts       # WebSocket client
│   ├── styles/
│   │   ├── main.css           # Tailwind imports
│   │   └── pacman-theme.css   # Design system Pac-Man (heredado)
│   ├── App.tsx
│   ├── main.tsx
│   └── types.ts
├── index.html
├── package.json
├── vite.config.ts
├── tsconfig.json
└── tailwind.config.ts
```

### 6.2 Estados do Sistema (Frontend)

```typescript
type SystemState = 'idle' | 'listening' | 'detecting' | 'stt' | 'processing' | 'tts' | 'error';
```

Correspondência visual (indicadores na UI):

| Estado | Cor | Ícone |
|--------|-----|-------|
| idle | Cinza `#6b7280` | Mic inativo |
| listening | Azul `#3b82f6` | Mic ativo |
| detecting | Ciano `#34d3ff` | Palpite (wake word detectado) |
| stt | Roxo `#8b5cf6` | Ouvindo fala |
| processing | Amarelo `#ffd166` | Processando (Hermes) |
| tts | Verde `#22c55e` | Falando |
| error | Vermelho `#ef4444` | Erro |

### 6.3 Navegação

A SPA terá 3 páginas/abas:

1. **Chat** (padrão) — Área de conversa + indicador de estado + botão de microfone
2. **Histórico** — Lista de interações anteriores com busca
3. **Configurações** — Painel completo de configuração

### 6.4 Integração com Design System Existente

O design system Pac-Man Tech Theme (`/design/css/styles.css`, `/design/js/scripts.js`) será adaptado:

- Paleta: ciano `#34d3ff`, amarelo `#ffd166`, fundo `#08101c`
- Font: Plus Jakarta Sans (Google Fonts)
- Estilo: glassmorphism, bordas neon, grid layout
- Pac-Man canvas: usado como background na página principal

## 7. Estrutura do Backend

```
backend/
├── main.py                  # Entry point, configuração do FastAPI
├── config/
│   ├── settings.py          # Pydantic settings + leitura de config.json
│   └── models.py            # Modelos de configuração (Pydantic)
├── api/
│   ├── __init__.py
│   ├── router.py            # Montagem de routers
│   ├── config.py            # GET/PUT /api/config
│   ├── history.py           # CRUD /api/history
│   ├── command.py           # POST /api/command
│   ├── test.py              # POST /api/test/*
│   └── websocket.py         # WebSocket endpoints
├── svc/
│   ├── __init__.py
│   ├── listening.py         # Loop principal de escuta
│   ├── wakeword.py          # Detecção de "Aurion"
│   ├── stt.py               # Speech-to-Text
│   ├── tts.py               # Text-to-Speech
│   └── hermes_bridge.py     # HTTP client para Hermes Agent
├── db/
│   ├── __init__.py
│   ├── database.py          # Conexão aiosqlite, migrations
│   ├── models.py            # ORM/queries para interactions
│   └── repo.py              # Repository pattern para dados
├── models/
│   ├── __init__.py
│   ├── interaction.py       # Modelos de interação (Pydantic)
│   └── response.py          # Modelos de resposta da API
├── requirements.txt         # Dependências Python
└── config.json              # Arquivo de configuração (não versionado)
```

## 8. Desenvolvimento Sequencial

### Build Order

1. **Setup do projeto** — Inicializar repositório, criar `backend/requirements.txt`, `frontend/package.json`, estrutura de diretórios
2. **Banco de dados** — Implementar `db/database.py` com aiosqlite, criar tabela `interactions`, escrever funções CRUD básicas
3. **Config Manager** — Implementar `config/settings.py` com pydantic-settings, leitura/escrita de `config.json`, endpoints REST de configuração
4. **Hermes Bridge** — Implementar `svc/hermes_bridge.py` com HTTP client, testar conexão com endpoint configurável
5. **API de comandos e histórico** — Implementar endpoints `POST /api/command`, `GET /api/history`, integração com Hermes Bridge e banco
6. **Wake Word Engine** — Implementar `svc/wakeword.py` com Porcupine, teste de detecção
7. **STT Service** — Implementar `svc/stt.py` com whisper.cpp (ggml-base Q4), integração com stream de áudio do PyAudio
8. **TTS Service** — Implementar `svc/tts.py` com edge-tts, geração e armazenamento de áudio
9. **Listening Service** — Implementar `svc/listening.py` com loop principal, integração de wake word + STT + Hermes + TTS
10. **WebSocket** — Implementar endpoints de WebSocket para status em tempo real e streaming de áudio TTS
11. **API completa** — Implementar todos os endpoints REST (testes, configurações avançadas)
12. **Frontend — Core** — Setup Vite + React + TypeScript, rotas, layout base, tema Pac-Man
13. **Frontend — Chat** — Implementar componentes de chat, integração com API REST e WebSocket
14. **Frontend — Configurações** — Painel de configurações com todos os campos, validação, botões de teste
15. **Frontend — Histórico** — Painel de histórico com busca e paginação
16. **Frontend — Microfone Web** — Implementar `useAudioRecorder` hook, MicButton, envio de áudio via WebSocket
17. **Frontend — Audio Player** — Reprodução de áudio TTS no navegador
18. **Integração e testes** — Testes E2E, ajustes de latência, documentação

**Dependências entre passos:**
- Passo 4 depende do 3 (Hermes Bridge usa configurações)
- Passo 5 depende dos passos 3 e 4 (comandos usam Hermes Bridge)
- Passos 6-8 são independentes entre si, mas dependem do 3
- Passo 9 depende dos passos 6, 7 e 8 (Listening Service orquestra os três)
- Passo 10 depende do 9 (WebSocket notifica estados do serviço)
- Passo 12 é independente (setup frontend)
- Passo 13 depende dos passos 5 e 10 (chat usa API e WebSocket)
- Passo 14 depende do 3 (configuração)
- Passo 15 depende do 5 (histórico)
- Passo 16 depende do 10 (WebSocket para áudio)
- Passo 17 depende do 8 (TTS)
- Passo 18 depende de todos os anteriores

## 9. Dependências

### Backend (`requirements.txt`)

```
fastapi==0.115+
uvicorn[standard]==0.34+
aiosqlite==0.21+
pydantic==2.10+
pydantic-settings==2.7+
httpx==0.28+
pyaudio==0.2.14
porcupine==1.3.2
whispercpp-python==1.1+    # Python bindings para whisper.cpp
edge-tts==7.0+
numpy==2.2+
```

### Frontend (`package.json` dependencies)

```json
{
  "dependencies": {
    "react": "^18.3+",
    "react-dom": "^18.3+",
    "react-router-dom": "^7.0+",
    "zustand": "^5.0+",
    "axios": "^1.7+",
    "@tailwindcss/vite": "^4.0+"
  },
  "devDependencies": {
    "typescript": "^5.7+",
    "vite": "^6.1+",
    "tailwindcss": "^4.0+",
    "@vitejs/plugin-react": "^4.3+"
  }
}
```

## 10. Tratamento de Erros

### 10.1 Cenários de Falha

| Cenário | Comportamento | UX |
|---------|--------------|-----|
| Hermes indisponível | Retry 3x com backoff exponencial, depois erro | Mensagem "Hermes indisponível" no chat |
| STT falha | Log de erro, tenta próxima engine (fallback) | Mensagem "Erro ao processar voz, tente texto" |
| TTS falha | Log de erro, retorna apenas texto | Texto na tela sem voz |
| Wake word falha | Log de erro, serviço continua em modo idle | Indicador de erro na UI |
| Microfone inacessível | Detecta permissão negada, orienta usuário | Modal com instruções de permissão |
| WebSocket desconecta | Auto-reconnect com backoff exponencial (max 5 tentativas) | Indicador de reconexão na UI |
| Banco de dados corrompido | Auto-backup antes de escrita, tenta reconstruir índice | Log de erro, mantém dados existentes |

### 10.2 Estrutura de Respostas de Erro

```python
class APIError(BaseModel):
    code: str          # "HERMES_UNAVAILABLE", "STT_ERROR", "TTS_ERROR", etc.
    message: str       # Mensagem legível em PT-BR
    details: dict | None = None
```

## 11. Segurança

- **Acesso local**: Por definição, apenas dispositivos na mesma rede local acessam a interface
- **Autenticação**: Não implementada na fase inicial (pergunta aberta no PRD), mas arquitetura suporta adicionar middleware de autenticação via header `Authorization`
- **Configuração sensível**: Token do Hermes armazenado em `config.json` com permissões restritas (não exposto via API)
- **CORS**: Configurado para permitir apenas origin da rede local durante desenvolvimento
- **HTTPS**: Não obrigatório localmente, mas recomendado para produção

## 12. Registros de Decisão de Arquitetura

1. **ADR-001** — [Arquitetura Servidor Local + Web App](adrs/adr-001.md) — Servidor local + web app em tempo real, rejeitando desktop app e microsserviços containerizados
2. **ADR-002** — [Stack de Backend Python com FastAPI](adrs/adr-002.md) — Python 3.11+ com FastAPI, uvicorn, aiosqlite, bibliotecas Python maduras para áudio/STT/TTS
3. **ADR-003** — [Arquitetura SPA Separada + FastAPI Backend](adrs/adr-003.md) — SPA React/TypeScript separada comunicando-se com FastAPI via HTTP REST e WebSocket
