# 🧠 Aurion — Framework de Assistente de IA por Voz

**Aurion** é um framework modular de assistente pessoal local-first, escrito em Python. Escuta continuamente a palavra de ativação pelo microfone, entra em conversas de voz com múltiplos turnos, encaminha comandos para um agente LLM externo (Hermes) e responde com síntese de voz de alta qualidade (Kokoro). Expõe uma API REST FastAPI e um painel web para monitoramento remoto e envio manual de comandos.

---

## 🚀 Funcionalidades

- 🎤 **Escuta contínua por voz** — detecção de palavra de ativação com correspondência aproximada, modo de conversa e supressão de eco
- 🧠 **Agente LLM externo** — comunicação com o Hermes Agent via API compatível com OpenAI (conecte qualquer backend compatível)
- 🔊 **Kokoro TTS** — síntese de voz de alta qualidade com divisão automática de texto para respostas longas
- 🔧 **6 ferramentas integradas** — horário, busca web (DuckDuckGo), OCR, captura de tela, varredura de rede e modo matrix
- 🌐 **API REST** — mais de 20 endpoints para comandos, histórico, status, logs, gerenciamento de voz e configuração de dispositivos de áudio
- 📡 **Descoberta de serviços mDNS** — detecta automaticamente serviços locais (Hermes, Kokoro, Whisper, Ollama)
- 💾 **Persistência SQLite** — armazena comandos, conversas, logs, configurações e transcrições
- 🔒 **Instância única** — impede a execução simultânea de múltiplas instâncias
- 🎛 **Painel web** — interface com tema Pac-Man para interação remota e monitoramento
- ✅ **Suite de testes abrangente** — mais de 73 casos de teste em 10 arquivos

---

## 🏗 Arquitetura

```
┌─────────────────────────────────────────────────────────────┐
│                        Serviço Aurion                       │
│                                                             │
│  ┌──────────────┐   ┌──────────────┐   ┌────────────────┐  │
│  │  Listener    │   │  Fila de     │   │  TTS           │  │
│  │  de Voz      │──▶│  Comandos    │──▶│  (Kokoro)      │  │
│  │  (thread)    │   │  (async)     │   │  (thread)      │  │
│  └──────────────┘   └──────────────┘   └────────────────┘  │
│        │                    │                                │
│        │                    ▼                                │
│        │            ┌──────────────┐                         │
│        │            │  Cliente     │                         │
│        │            │  Hermes      │                         │
│        │            │  (httpx)     │                         │
│        │            └──────┬───────┘                         │
│        │                   │                                 │
│        ▼                   ▼                                 │
│  ┌──────────────┐   ┌──────────────┐                         │
│  │  Dispositivos│   │  Banco       │                         │
│  │  de Áudio    │   │  SQLite      │                         │
│  │  (PyAudio)   │   │  (comandos,  │                         │
│  │              │   │   logs,      │                         │
│  │              │   │   configs)   │                         │
│  └──────────────┘   └──────────────┘                         │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Servidor FastAPI (uvicorn)               │   │
│  │  API REST + Painel Web Estático                       │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌──────────────┐   ┌──────────────────┐                    │
│  │  Descoberta  │   │  Lock de         │                    │
│  │  de Serviços │   │  Instância       │                    │
│  │  (mDNS)      │   │  (fcntl)         │                    │
│  └──────────────┘   └──────────────────┘                    │
└─────────────────────────────────────────────────────────────┘
```

---

## 📁 Estrutura do Projeto

```
Aurion/
├── aurion/                 # Framework modular do assistente
│   ├── __init__.py         # Metadados do pacote
│   ├── server.py           # Servidor FastAPI + endpoints REST
│   ├── listener.py         # Thread VoiceListener (palavra de ativação + conversa)
│   ├── tts.py              # TTSService (motor Kokoro)
│   ├── hermes.py           # HermesClient + VoiceConversationContext
│   ├── database.py         # Camada CRUD SQLite
│   ├── discovery.py        # Auto-descoberta de serviços mDNS
│   ├── greeting.py         # Geração e reprodução de áudio de saudação
│   ├── transcriptions.py   # Armazenamento de transcrições de áudio
│   ├── audio_devices.py    # Gerenciamento de microfone e alto-falante
│   ├── instance_lock.py    # Garantia de instância única
│   ├── tools/              # Ferramentas LangChain
│   │   ├── time.py         # get_time(city) — 26 cidades
│   │   ├── duckduckgo.py   # duckduckgo_search_tool(query)
│   │   ├── OCR.py          # read_text_from_latest_image()
│   │   ├── screenshot.py   # take_screenshot()
│   │   ├── arp_scan.py     # arp_scan_terminal()
│   │   └── matrix.py       # matrix_mode()
│   └── sounds/             # Arquivos de áudio de saudação gerados
│   └── static/             # Painel web (HTML, CSS, JS)
├── tests/                  # Suite pytest (73+ testes)
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
└── .env                    # Arquivo de configuração
```

---

## ⚙️ Configuração

Variáveis de ambiente (arquivo `.env`):

| Variável | Descrição | Padrão |
|----------|-----------|--------|
| `HERMES_BASE_URL` | URL da API do Hermes Agent | `http://localhost:8080` |
| `AURION_PORT` | Porta do servidor | `8080` |
| `TRIGGER_WORD` | Palavra de ativação (pronúncia: **Érmes**) | `ermes` |
| `TTS_VOICE_ID` | ID da voz Kokoro | _(seleção automática)_ |
| `KOKORO_BASE_URL` | URL da API Kokoro TTS | _(vazio / mesmo host)_ |
| `WHISPER_BASE_URL` | URL de transcrição Whisper | _(vazio / mesmo host)_ |

Ajustes do listener de voz (opcional):

| Variável | Descrição | Padrão |
|----------|-----------|--------|
| `VOICE_UTTERANCE_SILENCE_SEC` | Limiar de silêncio para fim da fala | `1.0` |
| `VOICE_WAKE_PHRASE_LIMIT` | Tamanho máximo da transcrição da palavra de ativação | `15` |
| `VOICE_ECHO_SIMILARITY` | Limiar de similaridade para detecção de eco | `0.80` |

---

## 🚀 Primeiros Passos

### 1. Instalar dependências

```bash
pip install -r requirements.txt
```

### 2. Configurar serviços externos

O Aurion depende de serviços externos que devem estar disponíveis na rede:

- **Hermes Agent** — backend LLM (API compatível com OpenAI, porta padrão `8080`)
- **Kokoro TTS** — síntese de voz (porta padrão `8000`)
- **Opcional**: Whisper ASR (`8001`), Ollama (`11434`)

O Aurion descobre esses serviços automaticamente via mDNS (zeroconf). Se não estiverem na mesma rede, configure manualmente no `.env`.

### 3. Executar o serviço

```bash
python -m aurion.server
```

Na inicialização, o Aurion irá:

1. Adquirir o lock de instância (impede execução duplicada)
2. Inicializar o banco de dados, dispositivos de áudio e todos os componentes
3. Reproduzir o áudio de saudação
4. Iniciar a thread do listener de voz
5. Subir o servidor FastAPI

---

## 🌐 API REST

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/api/command` | POST | Envia comando ao Hermes, obtém resposta e aciona TTS |
| `/api/conversations` | GET | Lista conversas com histórico de mensagens |
| `/api/conversations/{id}` | GET | Obtém uma conversa específica |
| `/api/history` | GET | Lista comandos com filtros de data e origem |
| `/api/history/{id}` | GET | Obtém detalhes de um comando específico |
| `/api/status` | GET | Status do servidor, estado de escuta e saúde dos serviços |
| `/api/logs` | GET | Logs com filtros de nível e componente |
| `/api/voices` | GET | Lista vozes TTS disponíveis |
| `/api/voices/{id}` | PUT | Define a voz padrão |
| `/api/voices/test` | POST | Testa uma voz com amostra de áudio |
| `/api/config` | GET/POST | Obtém/atualiza configuração |
| `/api/listen/start` | POST | Inicia a escuta por voz |
| `/api/listen/stop` | POST | Para a escuta por voz |
| `/api/listen/restart` | POST | Reinicia a escuta por voz |
| `/api/audio/devices` | GET | Lista todos os microfones e alto-falantes |
| `/api/audio/microphone` | POST | Define o microfone padrão |
| `/api/audio/speaker` | POST | Define o alto-falante padrão |
| `/api/transcriptions` | GET | Lista todas as transcrições de áudio |
| `/` | GET | Painel web ou JSON de status |

---

## 🧪 Testes

```bash
pytest
```

A suite cobre todos os módulos com mais de 73 casos de teste, incluindo detecção de palavra de ativação, CRUD do banco, cliente Hermes, TTS, endpoints REST, descoberta de serviços e mais.

---

## 🛠 Tecnologias

- **FastAPI** + **uvicorn** — servidor de API REST
- **httpx** — cliente HTTP assíncrono para o Hermes
- **SpeechRecognition** + **PyAudio** — entrada de microfone
- **Kokoro** — síntese de voz
- **python-zeroconf** — descoberta de serviços mDNS
- **SQLite** — persistência local de dados
- **pytest** + **pytest-asyncio** — framework de testes

---

## 📝 Observações

- **Local-first**: todo o processamento de voz e armazenamento de dados ocorrem localmente por padrão. Apenas a inferência LLM requer um Hermes Agent externo.
- **Privacidade**: nenhum dado sai da máquina, a menos que o Hermes Agent esteja configurado para um serviço externo.
- **Palavra de ativação**: o padrão é **Érmes** (configurado como `ermes`), com correspondência aproximada — suporta aliases como "hermes", "harmes", "airmes", além de correspondência parcial por prefixo ("er", "erm", "erme").
- **Modo conversa**: após a palavra de ativação, o Aurion entra em modo multi-turno. Para sair, diga "Érmes pare" ou "Érmes parar".
