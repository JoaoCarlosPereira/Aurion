# Aurion — Assistente Pessoal por Voz

> Framework de assistente pessoal que transforma o computador do usuário em um hub de controle por voz e texto para o Hermes Agent.

## Visão Geral

A Aurion escuta o ambiente, detecta a palavra **"Aurion"** como gatilho, processa o comando (via voz ou texto) e o encaminha ao Hermes Agent para execução. Após completar a tarefa, a Aurion confirma o resultado por voz, retornando a resposta pelo mesmo canal onde o comando foi recebido.

**Privada por definição**: todo o processamento de áudio, detecção de voz e execução de comandos ocorre localmente. Não há dados enviados para nuvens externas.

## Funcionalidades

| Recurso | Descrição |
|---------|-----------|
| 🎙️ Ativação por Wake Word | Detecção contínua da palavra "Aurion" com Vosk (offline) |
| 🗣️ Comando por Voz | Speech-to-Text com whisper.cpp (modelo base Q4, pt-BR) |
| ⌨️ Comando por Texto | Interface web para digitar comandos |
| 🔊 Resposta por Voz | Text-to-Speech com edge-tts (vozes pt-BR naturais) |
| 📡 Streaming de Áudio | Resposta TTS em streaming progressivo via WebSocket |
| 🌐 Controle Remoto | Interface web responsiva acessível de qualquer dispositivo na rede local |
| 📝 Histórico | Registro persistente de todas as interações com busca e paginação |
| ⚙️ Configuração | Painel completo para ajustar Hermes, STT, TTS, Wake Word e Áudio |

## Arquitetura

```
┌─────────────────────────────────────────────────┐
│                  Frontend (SPA)                   │
│  ┌───────────┬────────────┬──────────────────┐  │
│  │  Chat     │  History   │  Settings        │  │
│  │  Panel    │  Panel     │  Panel           │  │
│  └───────────┴────────────┴──────────────────┘  │
│  ┌──────────────────────────────────────────┐  │
│  │  WebSocket + HTTP API Client             │  │
│  └──────────────────────────────────────────┘  │
└────────────────────────┬───────────────────────┘
                         │ HTTP REST + WebSocket
┌────────────────────────┼───────────────────────┐
│                  Backend (FastAPI)               │
│  ┌───────────────────┬──────────────────────┐  │
│  │   API Router      │  WebSocket Manager   │  │
│  │   /api/command    │  /ws/status          │  │
│  │   /api/history    │  /ws/audio/          │  │
│  │   /api/config     │  /ws/voice-command/  │  │
│  └────────┬──────────┴──────────┬───────────┘  │
│           │                     │              │
│  ┌────────┴─────────────────────┴──────────┐  │
│  │       Listening Service (thread)         │  │
│  │  WakeWord → STT → Hermes → TTS          │  │
│  └─────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────┐  │
│  │  SQLite Database (aiosqlite)             │  │
│  └──────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
```

## Estrutura do Projeto

```
Aurion/
├── backend/                    # Python / FastAPI
│   ├── main.py                 # Entry point
│   ├── api/                    # Endpoints REST + WebSocket
│   │   ├── command.py          # POST /api/command
│   │   ├── history.py          # GET/DELETE /api/history
│   │   ├── config.py           # GET/PUT /api/config
│   │   ├── test.py             # POST /api/test/*
│   │   ├── websocket.py        # /ws/status, /ws/audio, /ws/voice-command
│   │   └── router.py           # Centralização de routers
│   ├── svc/                    # Serviços de negócio
│   │   ├── listening.py        # Loop principal de escuta
│   │   ├── wakeword.py         # Detecção de "Aurion"
│   │   ├── stt.py              # Speech-to-Text (whisper.cpp)
│   │   ├── tts.py              # Text-to-Speech (edge-tts)
│   │   └── hermes_bridge.py    # HTTP client para Hermes Agent
│   ├── db/                     # Persistência SQLite
│   │   ├── database.py         # Conexão e schema
│   │   ├── models.py           # Modelos Pydantic
│   │   └── repo.py             # Repository pattern
│   ├── config/                 # Configurações
│   │   ├── settings.py         # Config Manager
│   │   └── models.py           # Modelos Pydantic de config
│   ├── models/                 # Modelos da API
│   ├── tests/                  # Testes unitários e E2E
│   ├── requirements.txt        # Dependências Python
│   └── config.json.example     # Exemplo de configuração
├── frontend/                   # React / TypeScript / Vite
│   ├── src/
│   │   ├── components/         # Componentes React
│   │   │   ├── Chat/           # ChatPanel, ChatMessage, ChatInput
│   │   │   ├── History/        # HistoryPanel, HistorySearch, HistoryItem
│   │   │   ├── Settings/       # SettingsPanel + 5 sub-painéis
│   │   │   ├── MicButton/      # Botão flutuante de microfone
│   │   │   ├── AudioPlayer/    # Player com waveform
│   │   │   └── Status/         # SystemStatus, StatusIndicator
│   │   ├── hooks/              # Custom hooks
│   │   ├── store/              # Zustand store
│   │   ├── services/           # API + WebSocket clients
│   │   ├── styles/             # Tailwind + Pac-Man theme
│   │   └── types.ts            # Tipos TypeScript
│   ├── package.json
│   └── vite.config.ts
├── docs/                       # Documentação
│   ├── deployment.md           # Guia de instalação e deploy
│   ├── audio-config.md         # Configurações de áudio por SO
│   ├── troubleshooting.md      # Problemas comuns e soluções
│   └── metrics-report.md       # Métricas de sucesso
└── .docs/tasks/aurion-framework/ # Tasks e especificações
```

## Instalação

### Pré-requisitos

- **Python 3.11+** — [python.org](https://www.python.org/downloads/)
- **Node.js 18+** — [nodejs.org](https://nodejs.org/)
- **Git** — [git-scm.com](https://git-scm.com/)
- **PortAudio** — necessário para PyAudio (microfone/speaker)

### Instalação Automatizada (Ubuntu/Debian)

O script `install.sh` configura **todo o ambiente automaticamente**: dependências do sistema, ambiente virtual Python, dependências do frontend, modelo Vosk (pt-BR), configuração inicial, serviço systemd e firewall.

```bash
# Baixar e executar o instalador (requer sudo)
chmod +x install.sh
sudo ./install.sh
```

O script faz:

1. Instala dependências do sistema (Python, Node.js, PortAudio, build tools)
2. Verifica versões mínimas (Python ≥3.11, Node.js ≥18)
3. Cria ambiente virtual Python com todas as dependências do backend
4. Baixa o modelo Vosk para português (~31MB)
5. Instala dependências do frontend (npm)
6. Gera `config.json` a partir do exemplo
7. Configura serviço systemd para execução como serviço em produção
8. Configura firewall UFW (libera portas 8000 e 5173)
9. Realiza health check automático

Após a instalação, edite o arquivo de configuração:

```bash
nano backend/config.json
```

### Instalação Manual

**Configuração do PortAudio**

**Windows:**
```powershell
# Via vcpkg
vcpkg install portaudio:x64-windows
# Ou via conda
conda install -c conda-forge portaudio
```

**Linux:**
```bash
sudo apt-get install portaudio19-dev
```

**macOS:**
```bash
brew install portaudio
```

**Backend**

```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # Linux/macOS
.\venv\Scripts\activate         # Windows
pip install -r requirements.txt
```

**Frontend**

```bash
cd frontend
npm install
```

**Configuração**

```bash
# Copiar arquivo de exemplo
cp backend/config.json.example backend/config.json

# Editar com suas configurações (endpoint do Hermes, tokens, etc.)
nano backend/config.json
```

## Execução

### Modo Desenvolvimento

```bash
# Terminal 1 — Backend
cd backend
source venv/bin/activate        # Linux/macOS
.\venv\Scripts\activate         # Windows
uvicorn main:app --reload --port 8000

# Terminal 2 — Frontend
cd frontend
npm run dev
```

- **Backend:** `http://localhost:8000` (Swagger: `http://localhost:8000/docs`)
- **Frontend:** `http://localhost:5173`

### Modo Produção (systemd)

Após instalar via `install.sh`, o backend roda como serviço systemd:

```bash
sudo systemctl start aurion          # Iniciar
sudo systemctl stop aurion           # Parar
sudo systemctl restart aurion        # Reiniciar
sudo systemctl status aurion         # Status
sudo journalctl -u aurion -f         # Logs em tempo real
```

### Modo Produção (arquivos estáticos)

```bash
# 1. Build do frontend
cd frontend
npm run build

# 2. Servir os arquivos estáticos com nginx/apache
#    /api  -> localhost:8000
#    /ws   -> localhost:8000
#    resto -> frontend/dist/
```

## API Endpoints

### REST

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| `GET` | `/api/config` | Retorna todas as configurações |
| `PUT` | `/api/config` | Atualiza configurações (parcial) |
| `POST` | `/api/config/reset` | Restaura configurações padrão |
| `POST` | `/api/command` | Envia comando ao Hermes Agent |
| `GET` | `/api/command/{id}` | Consulta status de um comando |
| `GET` | `/api/history` | Lista interações (com busca/paginação) |
| `GET` | `/api/history/{id}` | Retorna interação específica |
| `DELETE` | `/api/history` | Limpa todo o histórico |
| `POST` | `/api/test/hermes` | Testa conexão com Hermes |
| `POST` | `/api/test/stt` | Testa serviço STT |
| `POST` | `/api/test/tts` | Testa serviço TTS |
| `GET` | `/api/test/tts/voices` | Lista vozes disponíveis |
| `GET` | `/api/health` | Health check |

### WebSocket

| Endpoint | Direção | Descrição |
|----------|---------|-----------|
| `/ws/status` | Server → Client | Estados do sistema |
| `/ws/audio/{session_id}` | Server → Client | Streaming TTS para browser |
| `/ws/voice-command/{session_id}` | Client → Server | Comandos por voz do browser |

## Estados do Sistema

| Estado | Cor | Descrição |
|--------|-----|-----------|
| idle | Cinza `#6b7280` | Ocioso, ouvindo |
| listening | Azul `#3b82f6` | Capturando áudio |
| detecting | Ciano `#34d3ff` | Wake word detectado |
| stt | Roxo `#8b5cf6` | Processando fala em texto |
| processing | Amarelo `#ffd166` | Enviando ao Hermes |
| tts | Verde `#22c55e` | Respondendo por voz |
| error | Vermelho `#ef4444` | Erro detectado |

## Testes

### Backend

```bash
cd backend
python -m pytest tests/ -v
```

- **Testes unitários:** ~120 testes (config, db, repo, hermes, wakeword, stt, tts, listening, api)
- **Testes E2E:** 22 testes (fluxo completo de comando, config, history, WS, error scenarios)
- **Testes de latência:** 16 testes de benchmark

```bash
# Testes E2E
python -m pytest tests/test_e2e.py -v

# Testes de latência
python -m pytest tests/test_latency.py -v --tb=no
```

## Métricas de Sucesso

| Critério | Status |
|----------|--------|
| Wake word < 1 segundo | ✅ Estimado ~100-500ms |
| Latência de resposta < 5 segundos | ⚠️ Estimado ~3-8s (depende de hardware) |
| Precisão STT > 90% | 📋 Depende do ambiente |
| Interface responsiva | ✅ Tailwind breakpoints |
| Operação 24/7 | ✅ Graceful shutdown |
| Cobertura de testes | ✅ 93-95% nos módulos principais |

## Documentação

| Documento | Descrição |
|-----------|-----------|
| [install.sh](install.sh) | Script de instalação automatizada para Ubuntu/Debian |
| [Deployment](docs/deployment.md) | Guia de instalação, configuração e deploy (systemd, Docker) |
| [Configurações de Áudio](docs/audio-config.md) | Configuração por SO (Windows/Linux/macOS) |
| [Troubleshooting](docs/troubleshooting.md) | Problemas comuns e soluções |
| [Métricas](docs/metrics-report.md) | Relatório de métricas de sucesso |

## Arquitetura (ADRs)

| ADR | Decisão |
|-----|---------|
| [ADR-001](.docs/tasks/aurion-framework/adrs/adr-001.md) | Arquitetura Servidor Local + Web App |
| [ADR-002](.docs/tasks/aurion-framework/adrs/adr-002.md) | Stack de Backend Python com FastAPI |
| [ADR-003](.docs/tasks/aurion-framework/adrs/adr-003.md) | SPA Separada + FastAPI Backend |

## Tecnologias

| Camada | Tecnologia |
|--------|------------|
| Backend | Python 3.11+, FastAPI, aiosqlite, Pydantic v2 |
| STT | whisper.cpp (modelo base Q4, pt-BR) |
| TTS | edge-tts (vozes pt-BR nativas) |
| Wake Word | Vosk (offline, sem API key) |
| Frontend | React 18+, TypeScript, Vite, Tailwind CSS 4, Zustand |
| Comunicação | REST API + WebSocket |
| Banco de dados | SQLite (aiosqlite, totalmente assíncrono) |

## Licença

Distribuído sob a [Licença Apache 2.0](LICENSE).
