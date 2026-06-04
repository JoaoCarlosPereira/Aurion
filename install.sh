#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# Aurion — Instalador Automatizado para Ubuntu/Debian
# =============================================================================
# Este script configura automaticamente o ambiente completo para executar a
# Aurion (assistente pessoal por voz) em sistemas Ubuntu/Debian.
#
# Uso:
#   chmod +x install.sh
#   sudo ./install.sh
#
# Requisitos mínimos:
#   - Ubuntu/Debian com sudo
#   - Conexão com internet
# =============================================================================

# --- Cores e formatação -------------------------------------------------------
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly CYAN='\033[0;36m'
readonly BOLD='\033[1m'
readonly NC='\033[0m'

info()    { echo -e "${BLUE}► $*${NC}"; }
success() { echo -e "${GREEN}✓ $*${NC}"; }
warn()    { echo -e "${YELLOW}⚠ $*${NC}"; }
error()   { echo -e "${RED}✗ $*${NC}"; }
section() { echo -e "\n${BOLD}${CYAN}═══ $* ═══${NC}"; }

# --- Verificações iniciais ----------------------------------------------------
if [[ $EUID -ne 0 ]]; then
    error "Este script deve ser executado com sudo."
    exit 1
fi

if [[ ! -f /etc/os-release ]]; then
    error "Sistema operacional não suportado. Este script é para Ubuntu/Debian."
    exit 1
fi

info "Detectado: $(cat /etc/os-release | grep PRETTY_NAME | cut -d= -f2 | tr -d '\"')"

# --- Configurações -------------------------------------------------------------
readonly PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly BACKEND_DIR="${PROJECT_DIR}/backend"
readonly FRONTEND_DIR="${PROJECT_DIR}/frontend"
readonly VENV_DIR="${BACKEND_DIR}/venv"
readonly PYTHON_MIN_VERSION="3.11"
readonly NODE_MIN_VERSION="18"
readonly SERVICE_NAME="aurion"
readonly SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
readonly CONFIG_SOURCE="${BACKEND_DIR}/config.json.example"
readonly CONFIG_TARGET="${BACKEND_DIR}/config.json"

# --- Funções utilitárias -------------------------------------------------------
check_command() { command -v "$1" &>/dev/null; }

get_version() {
    local cmd="$1"
    local pattern="$2"
    local version_output
    version_output=$("$cmd" --version 2>&1 | head -n1)
    echo "$version_output" | grep -oP "$pattern" | head -n1
}

compare_version() {
    local required="$1"
    local actual="$2"
    [[ "$(printf '%s\n' "$required" "$actual" | sort -V | head -n1)" == "$required" ]];
}

# --- 1. Dependências do sistema -----------------------------------------------
section "1. Instalando dependências do sistema"

info "Atualizando repositórios..."
apt-get update -y

info "Instalando pacotes necessários..."
apt-get install -y \
    python3 python3-venv python3-dev python3-pip \
    nodejs npm \
    git \
    portaudio19-dev \
    build-essential \
    libpulse-dev \
    libasound2-dev \
    curl \
    wget \
    ufw \
    jq

success "Dependências do sistema instaladas."

# --- 2. Verificação de versões -------------------------------------------------
section "2. Verificando versões"

# Python
PYTHON_VERSION=""
if check_command python3; then
    PYTHON_VERSION=$(get_version python3 '(\d+\.\d+)')
fi

if [[ -z "$PYTHON_VERSION" ]]; then
    error "Python 3 não encontrado. Instalando..."
    apt-get install -y python3 python3-venv python3-dev
    PYTHON_VERSION=$(get_version python3 '(\d+\.\d+)')
fi

if ! compare_version "$PYTHON_MIN_VERSION" "$PYTHON_VERSION"; then
    error "Python ${PYTHON_MIN_VERSION}+ necessário. Versão atual: ${PYTHON_VERSION}"
    error "Instale via: sudo apt install python3.11 python3.11-venv python3.11-dev"
    exit 1
fi
success "Python ${PYTHON_VERSION} (mínimo: ${PYTHON_MIN_VERSION})"

# Node.js
NODE_VERSION=""
if check_command node; then
    NODE_VERSION=$(get_version node '(\d+)')
fi

if [[ -z "$NODE_VERSION" ]]; then
    error "Node.js ${NODE_MIN_VERSION}+ não encontrado."
    info "Adicionando repositório Node.js LTS..."
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
    apt-get install -y nodejs
    NODE_VERSION=$(get_version node '(\d+)')
fi

if ! compare_version "$NODE_MIN_VERSION" "$NODE_VERSION"; then
    error "Node.js ${NODE_MIN_VERSION}+ necessário. Versão atual: ${NODE_VERSION}"
    exit 1
fi
success "Node.js ${NODE_VERSION} (mínimo: ${NODE_MIN_VERSION})"

# Git
if check_command git; then
    success "Git $(git --version | awk '{print $3}')"
else
    error "Git não encontrado. Instalando..."
    apt-get install -y git
    success "Git $(git --version | awk '{print $3}')"
fi

# --- 3. Ambiente virtual Python -----------------------------------------------
section "3. Configurando ambiente virtual Python"

if [[ -d "$VENV_DIR" ]]; then
    warn "Ambiente virtual já existe em ${VENV_DIR}"
    info "Recriando..."
    rm -rf "$VENV_DIR"
fi

info "Criando ambiente virtual em ${VENV_DIR}..."
python3 -m venv "$VENV_DIR"

info "Atualizando pip, setuptools e wheel..."
"${VENV_DIR}/bin/pip" install --upgrade pip setuptools wheel

info "Instalando dependências do backend..."
pip install -r requirements.txt --prefix="$VENV_DIR" 2>/dev/null || \
    "${VENV_DIR}/bin/pip" install -r "${BACKEND_DIR}/requirements.txt"

success "Dependências do backend instaladas."

# --- 4. Dependências do Frontend ---------------------------------------------
section "4. Configurando Frontend"

if [[ -d "${FRONTEND_DIR}/node_modules" ]]; then
    warn "node_modules já existe. Instalando novamente..."
fi

info "Instalando dependências do frontend..."
cd "$FRONTEND_DIR"
npm install

success "Dependências do frontend instaladas."

# --- 5. Configuração ----------------------------------------------------------
section "5. Configurando arquivo config.json"

if [[ -f "$CONFIG_TARGET" ]]; then
    warn "Arquivo de configuração já existe: ${CONFIG_TARGET}"
    info "Backup criado: ${CONFIG_TARGET}.bak"
    cp "$CONFIG_TARGET" "${CONFIG_TARGET}.bak"
fi

if [[ -f "$CONFIG_SOURCE" ]]; then
    cp "$CONFIG_SOURCE" "$CONFIG_TARGET"
    success "config.json criado a partir do exemplo."
    warn "EDITE ${CONFIG_TARGET} para configurar seu Hermes Agent e outras opções."
    warn "Edição recomendada: nano ${CONFIG_TARGET}"
else
    error "Arquivo config.json.example não encontrado em ${BACKEND_DIR}"
    exit 1
fi

# --- 6. Serviço systemd (produção) -------------------------------------------
section "6. Configurando serviço systemd (produção)"

readonly BACKEND_USER="$(whoami)"

cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=Aurion Voice Assistant Backend
After=network.target

[Service]
Type=simple
User=${BACKEND_USER}
WorkingDirectory=${BACKEND_DIR}
Environment="PATH=${VENV_DIR}/bin"
ExecStart=${VENV_DIR}/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=${SERVICE_NAME}

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "${SERVICE_NAME}"

success "Serviudo systemd '${SERVICE_NAME}' configurado."
warn "Inicie o serviço com: sudo systemctl start ${SERVICE_NAME}"
warn "Verifique o status com: sudo systemctl status ${SERVICE_NAME}"

# --- 7. Firewall ---------------------------------------------------------------
section "7. Configurando firewall (UFW)"

if command -v ufw &>/dev/null; then
    info "Verificando UFW..."
    ufw_status=$(ufw status 2>/dev/null | head -n1)

    if echo "$ufw_status" | grep -qi "active"; then
        ufw allow 8000/tcp 2>/dev/null || true
        ufw allow 5173/tcp 2>/dev/null || true
        success "Firewall configurado: portas 8000 e 5173 liberadas."
    else
        warn "UFW não está ativo. Para ativar:"
        warn "  sudo ufw allow 8000/tcp"
        warn "  sudo ufw allow 5173/tcp"
        warn "  sudo ufw enable"
    fi
else
    warn "UFW não instalado. Libere manualmente as portas 8000 e 5173."
fi

# --- 8. Verificação final -----------------------------------------------------
section "8. Verificação final"

# Health check do backend
if check_command curl; then
    sleep 2
    health=$(curl -s http://localhost:8000/api/health 2>/dev/null || echo "unreachable")
    if [[ "$health" != "unreachable" ]]; then
        success "Backend respondendo: ${health}"
    else
        warn "Backend não respondendo. Execute: sudo systemctl start ${SERVICE_NAME}"
    fi
fi

# --- Resumo final --------------------------------------------------------------
section "Instalação concluída!"

echo -e "${BOLD}Resumo:${NC}"
echo -e "  Python:    ${PYTHON_VERSION}"
echo -e "  Node.js:   ${NODE_VERSION}"
echo -e "  Backend:   ${VENV_DIR}"
echo -e "  Frontend:  ${FRONTEND_DIR}"
echo -e "  Config:    ${CONFIG_TARGET}"
echo -e "  Serviço:   ${SERVICE_NAME}"

echo -e "\n${BOLD}Comandos úteis:${NC}"
echo -e "  ${CYAN}Desenvolvimento (backend):${NC}  cd ${BACKEND_DIR} && ${VENV_DIR}/bin/uvicorn main:app --reload --port 8000"
echo -e "  ${CYAN}Desenvolvimento (frontend):${NC} cd ${FRONTEND_DIR} && npm run dev"
echo -e "  ${CYAN}Produção (serviço):${NC}         sudo systemctl start ${SERVICE_NAME}"
echo -e "  ${CYAN}Logs do serviço:${NC}            sudo journalctl -u ${SERVICE_NAME} -f"
echo -e "  ${CYAN}Swagger API:${NC}                http://localhost:8000/docs"

echo -e "\n${BOLD}${GREEN}A Aurion está pronta!${NC}\n"
echo -e "${YELLOW}Lembre-se de editar ${CONFIG_TARGET} com suas configurações antes de usar.${NC}"
