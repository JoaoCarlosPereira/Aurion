# Aurion — Framework de Assistente Pessoal por Voz

## Visão Geral

A Aurion é um framework de assistente pessoal que transforma o computador do usuário em um hub de controle por voz e texto para o Hermes Agent. Ela escuta o ambiente, detecta a palavra "Aurion" como gatilho, processa o comando (via voz ou texto) e o encaminha ao Hermes Agent para execução. Após completar a tarefa, a Aurion confirma o resultado por voz, retornando a resposta pelo mesmo canal onde o comando foi recebido.

A Aurion é privada por definição: todo o processamento de áudio, detecção de voz e execução de comandos ocorre localmente. Não há dados enviados para nuvens externas. A interface web funciona como controle remoto acessível de qualquer dispositivo na mesma rede local, mas o cérebro do sistema roda exclusivamente no computador do usuário.

## Objetivos

1. **Controle natural**: Permitir que o usuário interaja com o Hermes Agent de forma conversacional, por voz ou texto, como faria com um assistente humano.
2. **Privacidade total**: Todo processamento de áudio e execução de comandos permanece no ambiente local do usuário.
3. **Acesso multi-dispositivo**: Uma interface web responsiva permite que qualquer pessoa com acesso à rede local controle a Aurion de qualquer navegador.
4. **Resposta por voz contextual**: A Aurion responde por voz pelo mesmo dispositivo/canal que recebeu o comando, criando uma experiência coesa.
5. **Ativação por wake word**: O sistema ouve continuamente e reage apenas quando a palavra "Aurion" é detectada, sem intervenção manual.

## Histórias de Usuário

### HU-1: Ativação por Voz
**Como** usuário do Aurion,  
**Quero** que o sistema ouça continuamente meu microfone e reaja quando eu disser "Aurion",  
**Para que** eu possa interagir de forma natural, sem precisar apertar botões.

### HU-2: Comando por Voz
**Como** usuário do Aurion,  
**Quero** que meu fala seja convertida em texto e enviada ao Hermes Agent após a palavra de ativação,  
**Para que** eu possa dar comandos apenas falando.

### HU-3: Comando por Texto
**Como** usuário do Aurion,  
**Quero** digitar comandos na interface web para enviar ao Hermes Agent,  
**Para que** eu possa controlar o assistente sem precisar falar.

### HU-4: Resposta por Voz
**Como** usuário do Aurion,  
**Quero** que a Aurion me responda por voz após executar um comando,  
**Para que** eu saiba o resultado da tarefa sem precisar ler na tela.

### HU-5: Resposta no Canal Correto
**Como** usuário do Aurion,  
**Quero** que a resposta de voz saia pelo mesmo canal onde o comando foi dado (web ou servidor local),  
**Para que** a experiência seja consistente e contextual.

### HU-6: Controle Remoto via Web
**Como** usuário do Aurion,  
**Quero** acessar a interface web de qualquer dispositivo na minha rede para controlar a Aurion,  
**Para que** eu possa usar meu celular ou tablet para dar comandos ao meu computador principal.

### HU-7: Voz Configurável
**Como** usuário do Aurion,  
**Quero** escolher a voz da Aurion através de configurações da API,  
**Para que** o assistente tenha uma identidade sonora que eu goste.

### HU-8: Histórico de Comandos
**Como** usuário do Aurion,  
**Quero** visualizar um registro dos comandos enviados e respostas recebidas na interface web,  
**Para que** eu possa revisar o que foi feito.

### HU-9: Resposta por Texto na Tela
**Como** usuário do Aurion,  
**Quero** que o resultado do comando também apareça como texto na interface web,  
**Para que** eu possa ler a resposta mesmo sem áudio.

## Funcionalidades Principais

### 1. Detecção de Wake Word ("Aurion")
- Microfone do servidor monitora continuamente o ambiente
- Modelo local de detecção da palavra "Aurion" ativa instantaneamente
- Indicador visual na interface web mostra quando o sistema está ouvindo

### 2. Processamento de Comandos por Voz
- Fala do usuário é convertida em texto (STT) após o wake word
- Texto é enviado ao Hermes Agent para execução
- Timeout de silêncio encerra a captura de fala automaticamente

### 3. Interface Web de Controle
- Painel responsivo para enviar comandos por texto
- Exibição de respostas (texto e áudio) em tempo real
- Indicador visual do estado do sistema (ouvindo, processando, respondendo, ocioso)

### 4. Sistema de Resposta por Voz (TTS)
- Aurion fala a confirmação do comando executado
- Resposta sai pelo mesmo canal do comando (web ou servidor)
- Voz configurável via API de configurações

### 5. Integração com Hermes Agent
- Comunicação bidirecional com o Hermes Agent
- Comandos do usuário são encaminhados ao Hermes
- Resultados do Hermes são retornados ao usuário
- Status de execução visível na interface web

### 6. Painel de Configuração
- Página dedicada de configurações na interface web
- Configuração de acesso ao Hermes Agent (endereço, porta, token de autenticação)
- Configuração do serviço STT (Speech-to-Text): endpoint, chave de API, modelo
- Configuração do serviço TTS (Text-to-Speech): endpoint, chave de API, modelo, voz
- Seleção e personalização da voz da Aurion
- Ajuste de sensibilidade do wake word, idioma e volume
- Teste integrado: botão para testar cada conexão (Hermes, STT, TTS) diretamente do painel
- Persistência das configurações no servidor local

### 7. Histórico de Interações
- Registro persistente de todos os comandos e respostas
- Visualização cronológica na interface web
- Possibilidade de buscar comandos anteriores

### 8. Design Responsivo
- Interface adaptada para desktop, tablet e celular
- Seguindo o design system existente (Pac-Man Tech Theme) com paleta ciano/amarelo
- Navegação fluida entre dispositivos

## Experiência do Usuário

### Fluxo Principal
1. A Aurion roda silenciosamente no servidor, ouvindo o microfone
2. O usuário diz "Aurion" + seu comando (ex: "Aurion, liste os arquivos do projeto")
3. Um indicador visual pisca na interface web mostrando que o wake word foi detectado
4. O sistema captura a fala, converte em texto e envia ao Hermes Agent
5. O Hermes executa o comando e retorna o resultado
6. A Aurion fala a confirmação e exibe o resultado como texto na tela
7. O fluxo volta ao estado de espera

### Experiência na Interface Web
- Dashboard limpo com tema escuro (paleta ciano #34d3ff e amarelo #ffd166)
- Área principal mostrando as conversas em formato de chat
- Indicador de estado com cores: azul (ouvindo), verde (processando), amarelo (respondendo), cinza (ocioso)
- Botão flutuante de microfone na interface web para ativar o microfone do navegador
- Campo de texto para comandos manuais ao lado do botão de envio
- Menu/aba de configurações com página dedicada para configurar Hermes Agent, STT e TTS via API

### Experiência de Controle Remoto
- Acessar `http://<IP-DO-SERVIDOR>:PORTA` de qualquer navegador
- Interface idêntica em desktop e mobile
- Sessão persistente — histórico de conversas mantido durante o uso

## Fora de Escopo

- Controle por voz de dispositivos IoT ou smart home
- Assistente de tradução automática
- Reconhecimento de múltiplos usuários (voz única do proprietário)
- Integração com assistentes de terceiros (Siri, Google Assistant, Alexa)
- Execução de comandos em ambientes remotos (nuvem)
- Assistente visual com câmera

## Plano de Entrega por Fases

### Fase 1 — Núcleo (Core)
- Serviço local ouvindo o microfone
- Detecção do wake word "Aurion"
- Conversão de fala em texto (STT)
- Envio de comando ao Hermes Agent
- Interface web básica para envio de comandos por texto
- Exibição de respostas do Hermes como texto na interface web

### Fase 2 — Resposta por Voz e Controle
- Síntese de voz (TTS) para respostas da Aurion
- Reprodução da resposta pelo canal correto (web ou servidor)
- Voz configurável via API
- Indicadores visuais de estado do sistema

### Fase 3 — Controle Remoto e Refinamento
- Interface web responsiva completa (desktop + mobile)
- Histórico de interações
- Controle do microfone via navegador (botão de gravação na web)
- Aplicação do design system existente (Pac-Man Tech Theme)
- Configurações avançadas (sensibilidade, idioma, timeout)

## Métricas de Sucesso

1. **Latência de ativação**: Wake word detectado em menos de 1 segundo após ser dito
2. **Latência de resposta**: Comando executado e resposta dada em menos de 5 segundos
3. **Precisão do STT**: Comandos reconhecidos corretamente em mais de 90% das vezes em ambiente de ruído moderado
4. **Adoção do controle remoto**: Mais de 30% dos comandos vindo de dispositivos remotos (não do servidor local)
5. **Satisfação com a voz**: Usuário considera a voz da Aurion natural e agradável (avaliação subjetiva pós-configuração)
6. **Estabilidade do serviço**: Aurion opera 24/7 sem reinícios ou falhas no serviço de escuta

## Riscos e Mitigações

| Risco | Impacto | Mitigação |
|-------|---------|-----------|
| Ruído ambiente interfere na detecção do wake word | Alto — comandos acionados sem querer | Configurar sensibilidade do wake word; usar VAD para filtrar ruído de fundo |
| Hermes Agent indisponível ou com falha | Alto — comandos não são executados | Tratamento de erro na interface web; mensagem de erro clara para o usuário; retry automático |
| Configuração de áudio complexa no SO | Médio — fricção inicial de setup | Documentação clara de permissões de áudio; guia passo a passo por SO |
| Latência alta na resposta | Médio — experiência lenta e frustrante | Pipeline otimizado de STT → Hermes → TTS; feedback visual de loading imediato |
| Conflito de porta na rede local | Baixo — serviço não é acessível | Detectar porta em uso automaticamente; sugerir alternativa |
| Permissões de microfone no navegador | Baixo — controle remoto por voz falha | Instruções explícitas de permissão; fallback para comando por texto sempre disponível |

## Registros de Decisão de Arquitetura

| ADR | Título | Resumo |
|-----|--------|--------|
| [ADR-001](adrs/adr-001.md) | Arquitetura Servidor Local + Web App | Servidor local + web app em tempo real, rejeitando desktop app e microsserviços containerizados |

## Perguntas em Aberto

- Qual modelo de LLM o Hermes Agent utilizará como padrão? Isso impacta a latência da resposta
- Será necessário suporte para múltiplos idiomas na fala de entrada e na voz de resposta?
- Há necessidade de autenticação para acessar a interface web remotamente?
- A Aurion deve ter um nível de personalidade (tom de voz, formalidade) configurável?
- Qual será o comportamento da Aurion quando múltiplos dispositivos acessarem a interface web simultaneamente?
