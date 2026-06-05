# 🧠 Aurion — Voice-Controlled AI Assistant Framework

**Aurion** is a modular, local-first personal assistant framework built in Python. It continuously listens for a wake word via microphone, enters multi-turn voice conversations, routes commands to an external LLM agent (Hermes), and responds through high-quality text-to-speech (Kokoro). It exposes a FastAPI REST API and a web dashboard for remote monitoring and manual command entry.

---

## 🚀 Features

- 🎤 **Continuous voice listening** — wake word detection with fuzzy matching, conversation mode, echo suppression
- 🧠 **External LLM agent** — communicates with the Hermes Agent via OpenAI-compatible API (plug any compatible backend)
- 🔊 **Kokoro TTS** — high-quality voice synthesis with automatic text splitting for long responses
- 🔧 **6 built-in tools** — time lookup, web search (DuckDuckGo), OCR, screenshot, network scan, matrix mode
- 🌐 **REST API** — 20+ endpoints for commands, history, status, logs, voice management, audio device configuration
- 📡 **mDNS service discovery** — auto-detects local services (Hermes, Kokoro, Whisper, Ollama)
- 💾 **SQLite persistence** — stores commands, conversations, logs, settings, and transcriptions
- 🔒 **Single-instance enforcement** — prevents multiple instances from running simultaneously
- 🎛 **Web dashboard** — Pac-Man themed interface for remote interaction and monitoring
- ✅ **Comprehensive test suite** — 73+ test cases across 10 test files

---

## 🏗 Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Aurion Service                       │
│                                                             │
│  ┌──────────────┐   ┌──────────────┐   ┌────────────────┐  │
│  │  Voice       │   │  Command     │   │  TTS           │  │
│  │  Listener    │──▶│  Queue       │──▶│  (Kokoro)      │  │
│  │  (thread)    │   │  (async)     │   │  (thread)      │  │
│  └──────────────┘   └──────────────┘   └────────────────┘  │
│        │                    │                                │
│        │                    ▼                                │
│        │            ┌──────────────┐                         │
│        │            │  Hermes      │                         │
│        │            │  Client      │                         │
│        │            │  (httpx)     │                         │
│        │            └──────┬───────┘                         │
│        │                   │                                 │
│        ▼                   ▼                                 │
│  ┌──────────────┐   ┌──────────────┐                         │
│  │  Audio       │   │  SQLite      │                         │
│  │  Devices     │   │  Database    │                         │
│  │  (PyAudio)   │   │  (commands,  │                         │
│  │              │   │   logs,      │                         │
│  │              │   │   settings)  │                         │
│  └──────────────┘   └──────────────┘                         │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              FastAPI Server (uvicorn)                 │   │
│  │  REST API + Static Web Dashboard                      │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌──────────────┐   ┌──────────────────┐                    │
│  │  Service     │   │  Instance Lock   │                    │
│  │  Discovery   │   │  (fcntl)         │                    │
│  │  (mDNS)      │   │                  │                    │
│  └──────────────┘   └──────────────────┘                    │
└─────────────────────────────────────────────────────────────┘
```

---

## 📁 Project Structure

```
Jarvis/
├── aurion/                 # Modular assistant framework
│   ├── __init__.py         # Package metadata
│   ├── server.py           # FastAPI server + REST endpoints
│   ├── listener.py         # VoiceListener thread (wake word + conversation)
│   ├── tts.py              # TTSService (Kokoro engine)
│   ├── hermes.py           # HermesClient + VoiceConversationContext
│   ├── database.py         # SQLite CRUD layer
│   ├── discovery.py        # mDNS service auto-discovery
│   ├── greeting.py         # Greeting audio generation & playback
│   ├── transcriptions.py   # Audio transcription storage
│   ├── audio_devices.py    # Microphone/speaker device management
│   ├── instance_lock.py    # Single-instance enforcement
│   ├── tools/              # LangChain tools
│   │   ├── time.py         # get_time(city) — 26 cities
│   │   ├── duckduckgo.py   # duckduckgo_search_tool(query)
│   │   ├── OCR.py          # read_text_from_latest_image()
│   │   ├── screenshot.py   # take_screenshot()
│   │   ├── arp_scan.py     # arp_scan_terminal()
│   │   └── matrix.py       # matrix_mode()
│   └── sounds/             # Generated greeting audio files
│   └── static/             # Web dashboard (HTML, CSS, JS)
├── tests/                  # pytest test suite (73+ tests)
│   ├── conftest.py
│   ├── test_listener.py
│   ├── test_database.py
│   ├── test_hermes.py
│   ├── test_tts.py
│   ├── test_server.py
│   ├── test_discovery.py
│   ├── test_voice_context.py
│   ├── test_instance_lock.py
│   ├── test_package.py
│   └── test_tools.py
├── requirements.txt
├── pytest.ini
└── .env                    # Configuration file
```

---

## ⚙️ Configuration

Environment variables (`.env` file):

| Variable | Description | Default |
|----------|-------------|---------|
| `HERMES_BASE_URL` | Hermes Agent API URL | `http://localhost:8080` |
| `AURION_PORT` | Server port | `8080` |
| `TRIGGER_WORD` | Wake word | `aurion` |
| `TTS_VOICE_ID` | Kokoro voice ID | _(auto-select)_ |
| `KOKORO_BASE_URL` | Kokoro TTS API URL | _(empty / same host)_ |
| `WHISPER_BASE_URL` | Whisper transcription URL | _(empty / same host)_ |

Voice listener tuning (optional):

| Variable | Description | Default |
|----------|-------------|---------|
| `VOICE_UTTERANCE_SILENCE_SEC` | Silence threshold for end of utterance | `1.0` |
| `VOICE_WAKE_PHRASE_LIMIT` | Max wake word transcript length | `15` |
| `VOICE_ECHO_SIMILARITY` | Echo detection similarity threshold | `0.80` |

---

## 🚀 Getting Started

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Set up external services

Aurion depends on external services that must be available on your network:

- **Hermes Agent** — LLM backend (OpenAI-compatible API, default port `8080`)
- **Kokoro TTS** — Text-to-speech synthesis (default port `8000`)
- **Optional**: Whisper ASR (`8001`), Ollama (`11434`)

Aurion auto-discovers these services via mDNS (zeroconf). If not on the same network, configure them manually via `.env`.

### 3. Run the service

```bash
python -m aurion.server
```

On startup, Aurion will:
1. Acquire an instance lock (prevents double-running)
2. Initialize the database, audio devices, and all components
3. Play the greeting audio
4. Start the voice listener thread
5. Launch the FastAPI server

---

## 🌐 REST API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/command` | POST | Send a command to Hermes, get response, trigger TTS |
| `/api/conversations` | GET | List conversations with message history |
| `/api/conversations/{id}` | GET | Get a specific conversation |
| `/api/history` | GET | List commands with date/source filters |
| `/api/history/{id}` | GET | Get a specific command detail |
| `/api/status` | GET | Server status, listening state, service health |
| `/api/logs` | GET | Logs with level/component filters |
| `/api/voices` | GET | List available TTS voices |
| `/api/voices/{id}` | PUT | Set default voice |
| `/api/voices/test` | POST | Test a voice with audio sample |
| `/api/config` | GET/POST | Get/update configuration |
| `/api/listen/start` | POST | Start voice listening |
| `/api/listen/stop` | POST | Stop voice listening |
| `/api/listen/restart` | POST | Restart voice listening |
| `/api/audio/devices` | GET | List all microphones and speakers |
| `/api/audio/microphone` | POST | Set default microphone |
| `/api/audio/speaker` | POST | Set default speaker |
| `/api/transcriptions` | GET | List all audio transcriptions |
| `/` | GET | Web dashboard or status JSON |

---

## 🧪 Tests

```bash
pytest
```

The test suite covers all modules with 73+ test cases, including wake word detection, database CRUD, Hermes client, TTS, REST endpoints, service discovery, and more.

---

## 🛠 Built With

- **FastAPI** + **uvicorn** — REST API server
- **httpx** — Async HTTP client for Hermes
- **SpeechRecognition** + **PyAudio** — Microphone input
- **Kokoro** — Text-to-speech synthesis
- **python-zeroconf** — mDNS service discovery
- **SQLite** — Local data persistence
- **pytest** + **pytest-asyncio** — Test framework

---

## 📝 Notes

- **Local-first**: All voice processing and data storage happen locally by default. Only the LLM inference requires an external Hermes Agent.
- **Privacy**: No data leaves the machine unless the Hermes Agent is configured to an external service.
- **Wake word**: Default is "aurion" with fuzzy matching — supports aliases like "ario", "orion", "audio", plus partial prefix matching ("au", "aur").
- **Conversation mode**: After wake word, Aurion enters multi-turn mode. Exit by saying "aurion pare" or "aurion parar".
