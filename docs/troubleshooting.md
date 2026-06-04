# Guia de Troubleshooting — Aurion

## Visão Geral

Este guia cobre os problemas mais comuns ao instalar e executar o Aurion.

## Problemas de Instalação

### PyAudio não instala

**Sintoma:** `pip install pyaudio` falha com erro de compilação.

**Causa:** PortAudio não está instalado no sistema.

**Solução:**
```bash
# Windows - Via vcpkg
vcpkg install portaudio:x64-windows
# Ou via pip wheel pré-compilado
pip install pyaudio

# Linux
sudo apt-get install portaudio19-dev python3-dev

# macOS
brew install portaudio
```

### whispercpp-python não encontra modelo

**Sintoma:** `ImportError` ou `LibraryError` ao importar `whispercpp`.

**Causa:** Binário do whisper.cpp não disponível ou modelo ausente.

**Solução:**
```python
# O sistema faz fallback gracioso. Verifique o log:
# "whisper.cpp indisponível — usando fallback"
# Para instalar o modelo:
# Download: https://huggingface.co/ggerganov/whisper.cpp/tree/master/models
```

### Edge-tts falha

**Sintoma:** Erro ao sintetizar áudio com edge-tts.

**Solução:**
```python
# Verificar conexão com a Microsoft Edge TTS API
# O serviço pode ter limitações de uso
# Fallback automático para TTS externo está configurável
```

## Problemas de Áudio

### Microfone não detectado

**Sintoma:** PyAudio não encontra dispositivos de entrada.

**Soluções:**
1. Verificar permissões do sistema (Windows: Configurações → Privacidade → Microfone)
2. Verificar se o microfone está conectado e selecionado como padrão
3. Testar com `pactl list sources` (Linux) ou `system_profiler SPAudioDataType` (macOS)
4. Reiniciar o aplicativo após conectar o microfone

### Sem saída de áudio

**Sintoma:** TTS funciona mas não há som.

**Soluções:**
1. Verificar volume do sistema e do aplicativo
2. Verificar se o speaker está selecionado como padrão
3. Testar com `aplay` (Linux), Windows Sound Settings ou QuickTime Player (macOS)
4. Verificar se o PyAudio usa o dispositivo de saída correto

### Ruído de fundo excessivo

**Sintoma:** STT transcreve ruído como texto.

**Soluções:**
1. Ajustar `silence_threshold` no config.json (aumentar para ser mais seletivo)
2. Usar microfone com cancelamento de ruído
3. Diminuir `chunk_size` para menor latência de detecção de silêncio

### Latência alta na captura de áudio

**Sintoma:** Delay perceptível entre fala e processamento.

**Soluções:**
1. Diminuir `chunk_size` para 512-1024
2. Aumentar `threads` no config.json STT para mais paralelismo
3. Usar `ggml-tiny-q4` ou `ggml-base-q4` em vez de `medium` ou `large`
4. Verificar uso de CPU — reduzir outras aplicações

## Problemas de Conexão

### Hermes indisponível

**Sintoma:** Erros ao enviar comandos para o Hermes Agent.

**Diagnóstico:**
```bash
# Testar conexão
curl -X POST http://localhost:8000/api/test/hermes
# Ou verificar no painel de configurações web
```

**Soluções:**
1. Verificar se o Hermes Agent está rodando
2. Verificar `config.json` → `hermes.endpoint` está correto
3. Verificar `config.json` → `hermes.auth_token` está válido
4. Verificar firewall — porta do Hermes pode estar bloqueada
5. Verificar logs do Hermes Agent para erros

### WebSocket desconecta frequentemente

**Sintoma:** Frontend perde conexão com o backend.

**Causas comuns:**
1. CORS não configurado corretamente
2. Backend reiniciando (verificar logs)
3. Proxy reverso com timeout baixo
4. Rede instável (caso use deployment remoto)

**Soluções:**
1. Verificar CORS no backend: `CORSMiddleware` com origins corretas
2. Ajustar timeout do proxy (nginx: `proxy_read_timeout`)
3. Verificar auto-reconnect no frontend (já configurado com backoff exponencial)
4. Verificar se o WebSocket está na mesma porta que o HTTP

## Problemas do Frontend

### Frontend não conecta ao backend

**Sintoma:** Erros de rede no console do navegador.

**Soluções:**
1. Verificar se o backend está rodando na porta 8000
2. Verificar se o frontend está configurado com proxy no `vite.config.ts`
3. Verificar CORS: `app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"])`
4. Verificar se não há extensão de navegador bloqueando requisições

### Componentes não aparecem

**Sintoma:** Telas em branco ou componentes sem conteúdo.

**Soluções:**
1. Verificar console do navegador (F12) por erros de JavaScript
2. Verificar se as rotas estão corretas no `App.tsx`
3. Verificar se todos os imports estão resolvendo corretamente
4. Rodar `npm run build` para verificar erros de compilação

### Layout responsivo quebrado

**Sintoma:** Interface não se adapta a diferentes tamanhos de tela.

**Soluções:**
1. Verificar se o Tailwind CSS está carregando corretamente
2. Verificar se `pacman-theme.css` está sendo importado
3. Testar em diferentes breakpoints: mobile (375px), tablet (768px), desktop (1920px)

## Problemas de Performance

### Backend lento

**Sintoma:** Respostas da API demoram mais que o esperado.

**Diagnóstico:**
```bash
# Medir latência de cada endpoint
curl -w "@curl-format.txt" -o /dev/null -s http://localhost:8000/api/command

# Verificar uso de recursos
# top / task manager / Activity Monitor
```

**Otimizações:**
1. Aumentar `threads` no STT (se CPU tiver cores disponíveis)
2. Usar modelo whisper menor (`tiny` ou `base` em vez de `medium` ou `large`)
3. Reduzir `beam_size` no STT (trade-off velocidade/qualidade)
4. Verificar se não há outros processos consumindo CPU
5. Habilitar Gunicorn com múltiplos workers em produção

### Frontend lento

**Sintoma:** Interface responsiva lenta, especialmente em devices móveis.

**Otimizações:**
1. Reduzir número de mensagens renderizadas (virtualização de lista)
2. Otimizar imagens e recursos
3. Verificar se há re-renders desnecessários (usar React DevTools profiler)
4. Reduzir frequência de atualização do status WebSocket

## Logs e Debugging

### Logs do Backend

```python
# Configurar logging detalhado
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Logs do Frontend

```javascript
// Habilitar debug mode no Vite
// vite.config.ts: define: { __DEBUG__: JSON.stringify(true) }
```

### Comandos úteis

```bash
# Verificar se a porta 8000 está em uso
netstat -ano | findstr :8000  # Windows
lsof -i :8000                  # Linux/macOS

# Verificar saúde do backend
curl http://localhost:8000/api/health
curl http://localhost:8000/api/state

# Verificar se o database existe
ls backend/aurion.db

# Testar conexão WebSocket
wscat -c ws://localhost:8000/ws/status
```

## Problemas Comuns por Ordem de Frequência

| Problema | Frequência | Solução |
|---|---|---|
| PortAudio não instalado | Alta | Instalar via vcpkg/conda/homebrew |
| Hermes endpoint incorreto | Alta | Verificar config.json |
| CORS bloqueando requisições | Média | Configurar CORS no backend |
| Token do Hermes expirado | Média | Renovar token no Hermes |
| Modelo whisper não encontrado | Média | Download do modelo |
| Microfone sem permissão | Média | Configurar permissões do SO |
| WebSocket timeout | Baixa | Ajustar timeout do proxy |
| TTS falha | Baixa | Verificar conexão internet (edge-tts) |
| Memória insuficiente | Muito rara | Aumentar RAM ou usar modelo menor |

## Quando Criar um Issue

Se o problema não estiver listado aqui e as soluções não funcionarem:

1. Colete logs do backend (`uvicorn` output)
2. Colete logs do frontend (console do navegador)
3. Anote a versão do Python, Node.js e SO
4. Cole a saída de `pip list` e `npm list`
5. Descreva o comportamento esperado vs. o observado
