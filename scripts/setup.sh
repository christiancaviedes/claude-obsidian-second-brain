#!/usr/bin/env bash
#
# setup.sh - Initialize the Claude Obsidian Second Brain environment
#
# Usage: ./scripts/setup.sh
#

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Print colored message
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check Python version
check_python() {
    print_status "Checking Python installation..."

    # Try python3 first, then python
    if command -v python3 &> /dev/null; then
        PYTHON_CMD="python3"
    elif command -v python &> /dev/null; then
        PYTHON_CMD="python"
    else
        print_error "Python is not installed. Please install Python 3.10 or higher."
        exit 1
    fi

    # Check version
    PYTHON_VERSION=$($PYTHON_CMD -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    MAJOR_VERSION=$($PYTHON_CMD -c 'import sys; print(sys.version_info.major)')
    MINOR_VERSION=$($PYTHON_CMD -c 'import sys; print(sys.version_info.minor)')

    if [[ "$MAJOR_VERSION" -lt 3 ]] || { [[ "$MAJOR_VERSION" -eq 3 ]] && [[ "$MINOR_VERSION" -lt 10 ]]; }; then
        print_error "Python 3.10 or higher is required. Found: Python $PYTHON_VERSION"
        exit 1
    fi

    print_success "Found Python $PYTHON_VERSION"
}

# Create virtual environment
create_venv() {
    print_status "Creating virtual environment..."

    VENV_PATH="$PROJECT_ROOT/venv"

    if [[ -d "$VENV_PATH" ]]; then
        print_warning "Virtual environment already exists at $VENV_PATH"
        read -p "Do you want to recreate it? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -rf "$VENV_PATH"
            $PYTHON_CMD -m venv "$VENV_PATH"
            print_success "Virtual environment recreated"
        else
            print_status "Using existing virtual environment"
        fi
    else
        $PYTHON_CMD -m venv "$VENV_PATH"
        print_success "Virtual environment created at $VENV_PATH"
    fi
}

# Install dependencies
install_dependencies() {
    print_status "Installing dependencies..."

    VENV_PATH="$PROJECT_ROOT/venv"

    # Activate virtual environment
    source "$VENV_PATH/bin/activate"

    # Upgrade pip
    pip install --upgrade pip --quiet

    # Install requirements
    if [[ -f "$PROJECT_ROOT/requirements.txt" ]]; then
        pip install -r "$PROJECT_ROOT/requirements.txt"
        print_success "Dependencies installed from requirements.txt"
    else
        print_error "requirements.txt not found at $PROJECT_ROOT"
        exit 1
    fi

    deactivate
}

# Check and setup .env file
setup_env() {
    print_status "Checking environment configuration..."

    ENV_FILE="$PROJECT_ROOT/.env"
    ENV_EXAMPLE="$PROJECT_ROOT/.env.example"

    if [[ -f "$ENV_FILE" ]]; then
        print_success ".env file exists"
    else
        if [[ -f "$ENV_EXAMPLE" ]]; then
            print_warning ".env file not found"
            read -p "Would you like to create .env from .env.example? (Y/n): " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Nn]$ ]]; then
                cp "$ENV_EXAMPLE" "$ENV_FILE"
                print_success "Created .env from .env.example"
                print_warning "Please edit .env and add your API keys before running the converter"
            else
                print_warning "Skipping .env creation. You will need to create it manually."
            fi
        else
            print_warning ".env.example not found. Please create a .env file manually."
        fi
    fi
}

# Validate config files
validate_config() {
    print_status "Validating configuration files..."

    CONFIG_DIR="$PROJECT_ROOT/config"

    if [[ ! -d "$CONFIG_DIR" ]]; then
        print_warning "Config directory not found at $CONFIG_DIR"
        return
    fi

    # Check for expected config files
    EXPECTED_CONFIGS=("default.yaml" "config.yaml")

    for config in "${EXPECTED_CONFIGS[@]}"; do
        if [[ -f "$CONFIG_DIR/$config" ]]; then
            print_success "Found $config"
        fi
    done

    print_success "Configuration validation complete"
}

# Print next steps
print_next_steps() {
    echo ""
    echo -e "${GREEN}============================================${NC}"
    echo -e "${GREEN}  Setup Complete!${NC}"
    echo -e "${GREEN}============================================${NC}"
    echo ""
    echo "Next steps:"
    echo ""
    echo "  1. Configure your API keys in .env:"
    echo "     ${BLUE}nano $PROJECT_ROOT/.env${NC}"
    echo ""
    echo "  2. Export your Claude conversations:"
    echo "     - Visit claude.ai/settings"
    echo "     - Click 'Export Data'"
    echo "     - Download and extract the archive"
    echo ""
    echo "  3. Run the converter:"
    echo "     ${BLUE}./scripts/run.sh /path/to/claude-export${NC}"
    echo ""
    echo "  4. Open the output folder in Obsidian:"
    echo "     - Open Obsidian"
    echo "     - Click 'Open folder as vault'"
    echo "     - Select the output directory"
    echo ""
    echo "For more information, see README.md"
    echo ""
}

# Main execution
main() {
    echo ""
    echo -e "${BLUE}Claude Obsidian Second Brain - Setup${NC}"
    echo -e "${BLUE}=====================================${NC}"
    echo ""

    cd "$PROJECT_ROOT"

    check_python
    create_venv
    install_dependencies
    setup_env
    validate_config
    print_next_steps
}

main "$@"
