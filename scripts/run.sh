#!/usr/bin/env bash
#
# run.sh - Run the Claude to Obsidian converter
#
# Usage: ./scripts/run.sh /path/to/claude-export [/path/to/output]
#
# Arguments:
#   INPUT_PATH   - Path to exported Claude conversations (required)
#   OUTPUT_PATH  - Path for Obsidian vault output (optional, defaults to ./output)
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

# Show usage
usage() {
    echo "Usage: $0 INPUT_PATH [OUTPUT_PATH]"
    echo ""
    echo "Convert Claude AI conversation exports to an Obsidian vault."
    echo ""
    echo "Arguments:"
    echo "  INPUT_PATH   Path to exported Claude conversations (required)"
    echo "               This should be the extracted folder from Claude's export"
    echo ""
    echo "  OUTPUT_PATH  Path for Obsidian vault output (optional)"
    echo "               Defaults to ./output in the project directory"
    echo ""
    echo "Examples:"
    echo "  $0 ~/Downloads/claude-export"
    echo "  $0 ~/Downloads/claude-export ~/Documents/MySecondBrain"
    echo ""
    echo "Setup:"
    echo "  If you haven't set up the project yet, run:"
    echo "  ./scripts/setup.sh"
    echo ""
}

# Check if virtual environment exists
check_venv() {
    VENV_PATH="$PROJECT_ROOT/venv"

    if [[ ! -d "$VENV_PATH" ]]; then
        print_error "Virtual environment not found at $VENV_PATH"
        echo ""
        echo "Please run the setup script first:"
        echo "  ./scripts/setup.sh"
        echo ""
        exit 1
    fi

    if [[ ! -f "$VENV_PATH/bin/activate" ]]; then
        print_error "Virtual environment is corrupted (missing activate script)"
        echo ""
        echo "Please recreate the virtual environment by running:"
        echo "  ./scripts/setup.sh"
        echo ""
        exit 1
    fi
}

# Validate input path
validate_input() {
    local input_path="$1"

    if [[ ! -e "$input_path" ]]; then
        print_error "Input path does not exist: $input_path"
        exit 1
    fi

    if [[ ! -r "$input_path" ]]; then
        print_error "Input path is not readable: $input_path"
        exit 1
    fi

    print_success "Input path validated: $input_path"
}

# Check for .env file
check_env() {
    ENV_FILE="$PROJECT_ROOT/.env"

    if [[ ! -f "$ENV_FILE" ]]; then
        print_warning ".env file not found"
        print_warning "Some features may not work without API keys configured"
        echo ""
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_status "Exiting. Please configure .env first (see .env.example)"
            exit 0
        fi
    fi
}

# Run the converter
run_converter() {
    local input_path="$1"
    local output_path="$2"

    VENV_PATH="$PROJECT_ROOT/venv"

    print_status "Activating virtual environment..."
    source "$VENV_PATH/bin/activate"

    print_status "Running converter..."
    echo ""

    # Build command arguments
    CMD_ARGS=("--input" "$input_path")

    if [[ -n "$output_path" ]]; then
        CMD_ARGS+=("--output" "$output_path")
    fi

    # Run main.py with arguments
    cd "$PROJECT_ROOT"

    if [[ -f "$PROJECT_ROOT/src/main.py" ]]; then
        python "$PROJECT_ROOT/src/main.py" "${CMD_ARGS[@]}"
    elif [[ -f "$PROJECT_ROOT/main.py" ]]; then
        python "$PROJECT_ROOT/main.py" "${CMD_ARGS[@]}"
    else
        print_error "main.py not found in $PROJECT_ROOT or $PROJECT_ROOT/src"
        deactivate
        exit 1
    fi

    EXIT_CODE=$?

    deactivate

    if [[ $EXIT_CODE -eq 0 ]]; then
        echo ""
        print_success "Conversion complete!"
        echo ""
        echo "Your Obsidian vault is ready at: ${output_path:-$PROJECT_ROOT/output}"
        echo ""
        echo "To use it:"
        echo "  1. Open Obsidian"
        echo "  2. Click 'Open folder as vault'"
        echo "  3. Select the output directory"
        echo ""
    else
        print_error "Conversion failed with exit code $EXIT_CODE"
        exit $EXIT_CODE
    fi
}

# Main execution
main() {
    # Check for help flag
    if [[ "${1:-}" == "-h" ]] || [[ "${1:-}" == "--help" ]]; then
        usage
        exit 0
    fi

    # Check for required argument
    if [[ $# -lt 1 ]]; then
        print_error "Missing required argument: INPUT_PATH"
        echo ""
        usage
        exit 1
    fi

    INPUT_PATH="$1"
    OUTPUT_PATH="${2:-}"

    echo ""
    echo -e "${BLUE}Claude Obsidian Second Brain - Converter${NC}"
    echo -e "${BLUE}==========================================${NC}"
    echo ""

    check_venv
    check_env
    validate_input "$INPUT_PATH"
    run_converter "$INPUT_PATH" "$OUTPUT_PATH"
}

main "$@"
