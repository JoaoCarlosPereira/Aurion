# Configurações de Áudio por SO — Aurion

## Visão Geral

O Aurion utiliza PyAudio (wrapper de PortAudio) para captura e reprodução de áudio. Cada sistema operacional tem suas particularidades de configuração.

## Windows

### Pré-requisitos
- **PortAudio v19**: Necessário para o PyAudio funcionar
- **Driver de áudio**: Drivers padrão do Windows (WASAPI, DMAS)

### Instalação do PortAudio

**Via vcpkg:**
```powershell
git clone https://github.com/microsoft/vcpkg.git
cd vcpkg
.\bootstrap-vcpkg.bat
.\vcpkg install portaudio:x64-windows
```

**Via conda:**
```bash
conda install -c conda-forge portaudio
```

**Via pip (pré-compilado):**
```bash
pip install pyaudio
```

> Nota: PyPI geralmente oferece wheels pré-compilados para Windows. Se falhar, use vcpkg ou conda.

### Configuração de Dispositivos

Os dispositivos de áudio do Windows são acessados via WASAPI (modo exclusivo ou compartilhado).

```python
# Verificar dispositivos disponíveis
import pyaudio
audio = pyaudio.PyAudio()
for i in range(audio.get_device_count()):
    dev = audio.get_device_info_by_index(i)
    print(f"{i}: {dev['name']} - in:{dev['maxInputChannels']}, out:{dev['maxOutputChannels']}")
```

### Solução de Problemas

**Erro `PortAudio not found`:**
```powershell
# Instale via vcpkg
.\vcpkg\vcpkg install portaudio:x64-windows
.\vcpkg\vcpkg integrate install
```

**Microfone sem áudio:**
1. Verifique permissões: Configurações → Privacidade → Microfone
2. Teste o microfone no Gravador de Voz do Windows
3. Verifique se o dispositivo está como padrão

**Sem saída de áudio:**
1. Verifique se o speaker está selecionado como padrão
2. Verifique volume do sistema e do aplicativo

## Linux

### Pré-requisitos
- **PortAudio**: `sudo apt-get install portaudio19-dev`
- **ALSA ou PulseAudio/PipeWire**: Gerenciadores de áudio do Linux

### Instalação

```bash
# Instalar dependências do sistema
sudo apt-get install portaudio19-dev python3-dev

# Instalar PyAudio via pip
pip install pyaudio
```

### Configuração de Áudio

**ALSA:**
```bash
# Listar dispositivos ALSA
aplay -l  # saída
arecord -l  # entrada

# Testar gravação
arecord -d 5 test.wav
```

**PulseAudio:**
```bash
# Listar dispositivos PulseAudio
pactl list sources short
pactl list sinks short

# Testar reprodução
paplay /usr/share/sounds/alsa/Front_Center.wav
```

**PipeWire:**
```bash
# PipeWire é compatível com PulseAudio na maioria dos casos
pactl list sources short
pactl list sinks short
```

### Configuração no config.json

```json
{
  "audio": {
    "sample_rate": 16000,
    "channels": 1,
    "chunk_size": 1024,
    "silence_threshold": 300,
    "wake_word_timeout": 10
  }
}
```

- `chunk_size`: Em Linux com PulseAudio/PipeWire, valores de 1024-2048 funcionam bem
- `sample_rate`: 16000 é padrão para STT (whisper.cpp, Porcupine)
- `channels`: 1 (mono) para captura, reduz processamento

### Solução de Problemas

**Erro `ALSA lib`:**
```bash
# Instalar pacotes ALSA
sudo apt-get install alsa-utils alsa-ucm-conf
alsamixer  # Verificar volumes não-mudos
```

**Permissões de dispositivo:**
```bash
# Adicionar usuário ao grupo audio
sudo usermod -a -G audio $USER
# Re-login necessário
```

**Latência alta:**
```bash
# Ajustar buffer do PulseAudio
pactl set-default-sink 0
# Ou usar PipeWire com menor latência
```

## macOS

### Pré-requisitos
- **PortAudio**: Via Homebrew
- **CoreAudio**: Framework nativo do macOS (geralmente já disponível)

### Instalação

```bash
# Instalar PortAudio via Homebrew
brew install portaudio

# Instalar PyAudio
pip install pyaudio
```

### Configuração de Áudio

macOS usa CoreAudio nativamente, que oferece baixa latência e alta qualidade.

```bash
# Listar dispositivos de áudio
system_profiler SPAudioDataType

# Verificar dispositivos padrão
defaults read ~/Library/Preferences/com.apple.AudioVolumeState.plist
```

### Configuração no config.json

```json
{
  "audio": {
    "sample_rate": 16000,
    "channels": 1,
    "chunk_size": 1024,
    "silence_threshold": 300,
    "wake_word_timeout": 10
  }
}
```

### Solução de Problemas

**Permissões de microfone:**
1. Ajustes do Sistema → Privacidade e Segurança → Microfone
2. Permitir o Terminal/IDE acessar o microfone

**PortAudio não encontrado:**
```bash
# Verificar instalação
brew info portaudio

# Se ausente, instalar
brew install portaudio

# Verificar caminho
portaudio --version 2>/dev/null || echo "Verificar instalação manual"
```

**Erro de buffer:**
- macOS tem buffer interno do CoreAudio
- Ajuste `chunk_size` para 512-1024 se precisar de menor latência
- Para menor latência, use `silence_threshold` mais alto

## Configurações Comuns a Todos os SO

### sample_rate
- **16000 Hz**: Padrão para STT (whisper.cpp, Porcupine)
- **22050 Hz**: Boa qualidade para TTS
- **44100 Hz**: Qualidade CD (não recomendado para STT)

### channels
- **1 (mono)**: Recomendado para comando por voz
- **2 (estéreo)**: Não recomendado para STT (aumenta processamento sem benefício)

### chunk_size
- **512-1024**: Baixa latência (recomendado para wake word detection em tempo real)
- **2048-4096**: Equilíbrio entre latência e estabilidade
- **4096+**: Alta latência, mais estável

### silence_threshold
- **200-400**: Sensibilidade padrão para detecção de silêncio
- **Valores baixos**: Detecta silêncio mais rapidamente, pode cortar fala acidentalmente
- **Valores altos**: Mais tolerante, pode demorar para detectar fim da fala

### wake_word_timeout
- **5-15 segundos**: Tempo máximo de escuta após detectar wake word
- Se o usuário não falar dentro do timeout, volta ao modo de escuta do wake word

## Testes de Áudio

### Testar Microfone
```python
import pyaudio
import wave

CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
RECORD_SECONDS = 5

audio = pyaudio.PyAudio()
stream = audio.open(format=FORMAT, channels=CHANNELS,
                    rate=RATE, input=True, frames_per_buffer=CHUNK)

frames = []
for _ in range(0, RATE // CHUNK * RECORD_SECONDS):
    data = stream.read(CHUNK)
    frames.append(data)

stream.stop_stream()
stream.close()
audio.terminate()

# Salvar para verificar
wave_file = wave.open("test.wav", "wb")
wave_file.setnchannels(CHANNELS)
wave_file.setsampwidth(audio.get_sample_size(FORMAT))
wave_file.setframerate(RATE)
wave_file.writeframes(b"".join(frames))
wave_file.close()
print("Gravação salva em test.wav")
```

### Testar Speaker
```python
import pyaudio
import numpy as np

audio = pyaudio.PyAudio()
stream = audio.open(format=pyaudio.paInt16, channels=1,
                    rate=16000, output=True)

# Gerar tom de 440Hz por 1 segundo
frequency = 440
duration = 1.0
t = np.linspace(0, duration, int(16000 * duration))
tone = np.sin(2 * np.pi * frequency * t)
tone = (tone * 32767).astype(np.int16).tobytes()

stream.write(tone)
stream.stop_stream()
stream.close()
audio.terminate()
print("Tom de 440Hz reproduzido")
```

## Otimizações por SO

| SO | Melhor chunk_size | Melhor silêncio | Latência mínima |
|---|---|---|---|
| Windows | 2048 | 300 | ~100ms |
| Linux (Pulse) | 1024 | 250 | ~50ms |
| Linux (ALSA) | 1024 | 300 | ~30ms |
| macOS | 1024 | 250 | ~20ms |
