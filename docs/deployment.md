# Guia de Deployment — Aurion

## Pré-requisitos

### Sistema Operacional
- Windows 10/11 (ou WSL2 em Linux)
- macOS 12+ (via Homebrew)
- Linux Ubuntu/Debian 20.04+

### Software Necessário
- **Python 3.11+** — [python.org](https://www.python.org/downloads/)
- **Node.js 18+** — [nodejs.org](https://nodejs.org/)
- **Git** — [git-scm.com](https://git-scm.com/)
- **PortAudio** — necessário para PyAudio (microfone/speaker)

### Instalação do PortAudio

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

## Instalação do Backend

```bash
# Clonar o repositório
git clone <repo-url>
cd dsv-git/Aurion

# Criar ambiente virtual
python -m venv venv
.\venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/macOS

# Instalar dependências
cd backend
pip install -r requirements.txt
```

### Configuração

```bash
# Copiar arquivo de exemplo
cp config.json.example config.json

# Editar com suas configurações
# endpoints, tokens, caminhos de modelo, etc.
```

### Executar Backend

```bash
# Executar com uvicorn (modo desenvolvimento)
uvicorn main:app --reload --port 8000

# Executar em produção
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1
```

O backend estará disponível em `http://localhost:8000`
Documentação Swagger: `http://localhost:8000/docs`

## Instalação do Frontend

```bash
# Navegar ao diretório frontend
cd frontend

# Instalar dependências
npm install

# Executar em modo desenvolvimento
npm run dev
```

O frontend estará disponível em `http://localhost:5173`

### Build para Produção

```bash
# Build estática
npm run build

# O output será gerado em dist/
# Sirva os arquivos estáticos com um servidor web (nginx, apache, etc.)
```

## Configuração do config.json

```json
{
  "hermes": {
    "endpoint": "http://hermes-server:8080",
    "auth_token": "seu-token-aqui"
  },
  "stt": {
    "engine": "whisper.cpp",
    "model": "ggml-base-q4",
    "language": "pt",
    "threads": 4,
    "beam_size": 5,
    "max_context": -1
  },
  "tts": {
    "engine": "edge-tts",
    "voice": "pt-BR-FabioNeural",
    "rate": 0,
    "volume": 100,
    "external": {
      "enabled": false,
      "endpoint": "",
      "api_key": "",
      "stream_buffer_ms": 500,
      "format": "mp3",
      "timeout": 30
    }
  },
  "wake_word": {
    "engine": "vosk",
    "sensitivity": 0.5,
    "keyword": "",
    "keyword_path": "",
    "wake_word_timeout": 10
  },
  "audio": {
    "sample_rate": 16000,
    "channels": 1,
    "chunk_size": 2048,
    "silence_threshold": 300,
    "wake_word_timeout": 10
  },
  "database": {
    "path": "aurion.db"
  }
}
```

## Execução do Servidor

### Modo Desenvolvimento

```bash
# Terminal 1 — Backend
cd backend
.\venv\Scripts\activate
uvicorn main:app --reload --port 8000

# Terminal 2 — Frontend
cd frontend
npm run dev
```

### Modo Produção

```bash
# 1. Build do frontend
cd frontend
npm run build

# 2. Configurar proxy reverso (nginx exemplo)
#    /api -> localhost:8000
#    /ws  -> localhost:8000
#    resto -> frontend/dist/
```

## Ambiente de Produção

### systemd (Linux)

```ini
# /etc/systemd/system/aurion.service
[Unit]
Description=Aurion Voice Assistant Backend
After=network.target

[Service]
Type=simple
User=aurion
WorkingDirectory=/opt/aurion/backend
Environment="PATH=/opt/aurion/backend/venv/bin"
ExecStart=/opt/aurion/backend/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable aurion
sudo systemctl start aurion
sudo systemctl status aurion
```

### Docker (Opcional)

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## Verificação

```bash
# Health check
curl http://localhost:8000/api/health

# Status do sistema
curl http://localhost:8000/api/state

# Configurações
curl http://localhost:8000/api/config
```

## Troubleshooting Rápido

- **Erro de import PyAudio**: Instale o PortAudio (veja Pré-requisitos)
- **Erro de WebSocket**: Verifique se o CORS está configurado
- **Erro de conexão Hermes**: Verifique `config.json` e a URL do endpoint
- **Frontend não conecta**: Verifique se o backend está rodando na porta 8000
