#!/bin/bash
# Adaptive Framework - Universal Installer
# Works on: Linux, macOS, Termux (Android), WSL2

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Config
REPO="adaptive-framework"
INSTALL_DIR="${HOME}/.local/bin"
DATA_DIR="${HOME}/.adaptive_framework"
PYTHON_MIN_VERSION="3.10"

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Detect platform
detect_platform() {
    case "$(uname -s)" in
        Linux*)
            if grep -q "termux" /proc/version 2>/dev/null || [ -n "${TERMUX_VERSION:-}" ]; then
                PLATFORM="termux"
            elif grep -q "microsoft" /proc/version 2>/dev/null; then
                PLATFORM="wsl2"
            else
                PLATFORM="linux"
            fi
            ;;
        Darwin*)
            PLATFORM="macos"
            ;;
        CYGWIN*|MINGW*|MSYS*)
            PLATFORM="windows"
            ;;
        *)
            PLATFORM="unknown"
            ;;
    esac
    log_info "Detected platform: $PLATFORM"
}

# Check Python version
check_python() {
    log_info "Checking Python version..."
    
    if command -v python3 &> /dev/null; then
        PYTHON_CMD="python3"
    elif command -v python &> /dev/null; then
        PYTHON_CMD="python"
    else
        log_error "Python not found. Please install Python ${PYTHON_MIN_VERSION}+"
        exit 1
    fi
    
    PYTHON_VERSION=$($PYTHON_CMD -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    PYTHON_MAJOR=$($PYTHON_CMD -c "import sys; print(sys.version_info.major)")
    PYTHON_MINOR=$($PYTHON_CMD -c "import sys; print(sys.version_info.minor)")
    
    if [ "$PYTHON_MAJOR" -lt 3 ] || [ "$PYTHON_MAJOR" -eq 3 -a "$PYTHON_MINOR" -lt 10 ]; then
        log_error "Python ${PYTHON_MIN_VERSION}+ required, found ${PYTHON_VERSION}"
        exit 1
    fi
    
    log_success "Python ${PYTHON_VERSION} found"
}

# Install system dependencies
install_system_deps() {
    log_info "Installing system dependencies for $PLATFORM..."
    
    case $PLATFORM in
        termux)
            pkg update -y
            pkg install -y python git clang make libffi openssl
            ;;
        linux)
            if command -v apt &> /dev/null; then
                sudo apt update && sudo apt install -y python3 python3-pip python3-venv git build-essential libssl-dev libffi-dev
            elif command -v dnf &> /dev/null; then
                sudo dnf install -y python3 python3-pip git gcc make openssl-devel libffi-devel
            elif command -v pacman &> /dev/null; then
                sudo pacman -S --needed python python-pip git base-devel openssl libffi
            else
                log_warn "Unknown package manager. Please install Python 3.10+ manually."
            fi
            ;;
        macos)
            if command -v brew &> /dev/null; then
                brew install python git
            else
                log_warn "Homebrew not found. Please install from https://brew.sh"
            fi
            ;;
        wsl2)
            sudo apt update && sudo apt install -y python3 python3-pip python3-venv git build-essential libssl-dev libffi-dev
            ;;
        *)
            log_warn "Unknown platform. Please ensure Python 3.10+ is installed."
            ;;
    esac
}

# Setup Python environment
setup_python_env() {
    log_info "Setting up Python environment..."
    
    # Create virtual environment
    VENV_DIR="${DATA_DIR}/venv"
    $PYTHON_CMD -m venv "$VENV_DIR"
    
    # Activate
    source "${VENV_DIR}/bin/activate"
    
    # Upgrade pip
    pip install --upgrade pip setuptools wheel
    
    log_success "Virtual environment created at ${VENV_DIR}"
}

# Install Adaptive Framework
install_framework() {
    log_info "Installing Adaptive Framework..."
    
    # Install from local source (development) or PyPI
    if [ -f "pyproject.toml" ]; then
        log_info "Installing from local source..."
        pip install -e ".[all]"
    else
        log_info "Installing from PyPI..."
        pip install "adaptive-framework[all]"
    fi
    
    log_success "Adaptive Framework installed"
}

# Create launcher scripts
create_launchers() {
    log_info "Creating launcher scripts..."
    
    mkdir -p "$INSTALL_DIR"
    
    # Main CLI launcher
    cat > "${INSTALL_DIR}/adaptive" << 'EOF'
#!/bin/bash
# Adaptive Framework CLI Launcher

DATA_DIR="${HOME}/.adaptive_framework"
VENV_DIR="${DATA_DIR}/venv"

# Activate virtual environment
if [ -f "${VENV_DIR}/bin/activate" ]; then
    source "${VENV_DIR}/bin/activate"
fi

# Run CLI
exec adaptive-framework "$@"
EOF
    chmod +x "${INSTALL_DIR}/adaptive"
    
    # Web UI launcher
    cat > "${INSTALL_DIR}/adaptive-web" << 'EOF'
#!/bin/bash
# Adaptive Framework Web UI Launcher

DATA_DIR="${HOME}/.adaptive_framework"
VENV_DIR="${DATA_DIR}/venv"

if [ -f "${VENV_DIR}/bin/activate" ]; then
    source "${VENV_DIR}/bin/activate"
fi

exec adaptive-framework-web "$@"
EOF
    chmod +x "${INSTALL_DIR}/adaptive-web"
    
    # GUI launcher
    cat > "${INSTALL_DIR}/adaptive-gui" << 'EOF'
#!/bin/bash
# Adaptive Framework GUI Launcher

DATA_DIR="${HOME}/.adaptive_framework"
VENV_DIR="${DATA_DIR}/venv"

if [ -f "${VENV_DIR}/bin/activate" ]; then
    source "${VENV_DIR}/bin/activate"
fi

exec adaptive-framework-gui "$@"
EOF
    chmod +x "${INSTALL_DIR}/adaptive-gui"
    
    # Agent CLI launcher
    cat > "${INSTALL_DIR}/adaptive-agent" << 'EOF'
#!/bin/bash
# Adaptive Framework Agent CLI Launcher

DATA_DIR="${HOME}/.adaptive_framework"
VENV_DIR="${DATA_DIR}/venv"

if [ -f "${VENV_DIR}/bin/activate" ]; then
    source "${VENV_DIR}/bin/activate"
fi

exec adaptive-framework-agent "$@"
EOF
    chmod +x "${INSTALL_DIR}/adaptive-agent"
    
    log_success "Launchers created in ${INSTALL_DIR}"
}

# Initialize data directory
init_data_dir() {
    log_info "Initializing data directory..."
    
    mkdir -p "${DATA_DIR}/extensions"
    mkdir -p "${DATA_DIR}/logs"
    mkdir -p "${DATA_DIR}/cache"
    
    # Create default config
    cat > "${DATA_DIR}/config.yaml" << 'EOF'
# Adaptive Framework Configuration
model:
  provider: "auto"
  name: "auto"

tools:
  enabled:
    - "file_ops"
    - "shell"
    - "memory"
    - "learning"
    - "feedback"
    - "mcp"
    - "agent_loop"

skills:
  auto_create: true
  auto_improve: true

memory:
  backend: "sqlite"
  vector_enabled: true
  consolidation_interval: 3600

mcp:
  enabled: true
  servers: {}

webui:
  host: "0.0.0.0"
  port: 8080

gui:
  theme: "dark"
  window_size: "1200x800"

logging:
  level: "INFO"
  file: "logs/adaptive.log"
EOF
    
    log_success "Data directory initialized at ${DATA_DIR}"
}

# Add to PATH
setup_path() {
    log_info "Setting up PATH..."
    
    SHELL_RC=""
    if [ -n "${ZSH_VERSION:-}" ]; then
        SHELL_RC="${HOME}/.zshrc"
    elif [ -n "${BASH_VERSION:-}" ]; then
        SHELL_RC="${HOME}/.bashrc"
    else
        SHELL_RC="${HOME}/.profile"
    fi
    
    if [ -f "$SHELL_RC" ]; then
        if ! grep -q "${INSTALL_DIR}" "$SHELL_RC"; then
            echo "" >> "$SHELL_RC"
            echo "# Adaptive Framework" >> "$SHELL_RC"
            echo "export PATH=\"${INSTALL_DIR}:\${PATH}\"" >> "$SHELL_RC"
            log_success "Added ${INSTALL_DIR} to PATH in ${SHELL_RC}"
        else
            log_info "PATH already configured in ${SHELL_RC}"
        fi
    fi
    
    # Also add for current session
    export PATH="${INSTALL_DIR}:${PATH}"
}

# Verify installation
verify_installation() {
    log_info "Verifying installation..."
    
    # Check launchers
    for cmd in adaptive adaptive-web adaptive-gui adaptive-agent; do
        if [ -x "${INSTALL_DIR}/${cmd}" ]; then
            log_success "Launcher ${cmd} ready"
        else
            log_error "Launcher ${cmd} missing"
            return 1
        fi
    done
    
    # Test CLI
    if "${INSTALL_DIR}/adaptive" doctor 2>&1 | grep -q "Python"; then
        log_success "CLI working correctly"
    else
        log_warn "CLI test had issues (may need shell restart)"
    fi
}

# Main
main() {
    echo -e "${BLUE}"
    echo "╔══════════════════════════════════════════╗"
    echo "║   Adaptive Framework Installer v0.1.0   ║"
    echo "║   Self-improving AI Agent Platform       ║"
    echo "╚══════════════════════════════════════════╝"
    echo -e "${NC}"
    
    detect_platform
    check_python
    
    # Ask for system deps installation
    if [ "$PLATFORM" != "termux" ] && [ "$PLATFORM" != "unknown" ]; then
        read -p "Install system dependencies? (requires sudo) [y/N] " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            install_system_deps
        fi
    fi
    
    setup_python_env
    install_framework
    create_launchers
    init_data_dir
    setup_path
    verify_installation
    
    echo
    echo -e "${GREEN}╔══════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║   Installation Complete!                 ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════╝${NC}"
    echo
    echo "Next steps:"
    echo "  1. Restart your shell or run: source ~/.bashrc (or ~/.zshrc)"
    echo "  2. Run 'adaptive doctor' to verify"
    echo "  3. Run 'adaptive run \"your goal\"' to start"
    echo "  4. Run 'adaptive-web' for Web UI"
    echo "  5. Run 'adaptive-gui' for Desktop GUI"
    echo
    echo "Data directory: ${DATA_DIR}"
    echo "Config file: ${DATA_DIR}/config.yaml"
}

# Run if executed directly
if [ "${BASH_SOURCE[0]}" == "${0}" ]; then
    main "$@"
fi