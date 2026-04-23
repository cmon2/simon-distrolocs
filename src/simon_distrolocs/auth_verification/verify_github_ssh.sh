#!/bin/bash
# verify_github_ssh_auth.sh - Verify SSH authentication to GitHub
# Usage: verify_github_ssh_auth.sh [token_path]
#   token_path: Path to SSH private key file (optional, auto-detected)
#
# Exits: 0 on success, 1 on failure

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# simon_ide/ is 7 levels up from auth_verification/
# auth_verification/ -> simon_distrolocs/ -> src/ -> simon-distrolocs/ -> git-repos/ -> simon-public-github-repos/ -> 06_agents_working_directory/ -> simon_ide/
SIMON_IDE_DIR="$(cd "$SCRIPT_DIR/../../../../../../.." && pwd)"

verify_github_ssh() {
    local key_path="${1:-}"

    echo "Verifying GitHub SSH authentication..."
    echo ""

    # Auto-detect key path if not provided
    if [ -z "$key_path" ]; then
        if [ -f "$SIMON_IDE_DIR/02_configs/git/GitHub/id_ed25519" ]; then
            key_path="$SIMON_IDE_DIR/02_configs/git/GitHub/id_ed25519"
        elif [ -f "$SIMON_IDE_DIR/02_configs/git/GitHub/id_rsa" ]; then
            key_path="$SIMON_IDE_DIR/02_configs/git/GitHub/id_rsa"
        elif [ -f "$HOME/.ssh/id_ed25519" ]; then
            key_path="$HOME/.ssh/id_ed25519"
        elif [ -f "$HOME/.ssh/id_rsa" ]; then
            key_path="$HOME/.ssh/id_rsa"
        else
            echo "[ERROR] No SSH key found for GitHub"
            echo "Expected at: $SIMON_IDE_DIR/02_configs/git/GitHub/id_ed25519 or id_rsa"
            return 1
        fi
    fi

    echo "  Using key: $key_path"

    if [ ! -f "$key_path" ]; then
        echo "[ERROR] Key file not found: $key_path"
        return 1
    fi

    # Test SSH connection to GitHub
    echo "  Testing SSH connection to github.com..."

    local output
    local exit_code

    output=$(ssh -T -o StrictHostKeyChecking=no -o IdentitiesOnly=yes -i "$key_path" git@github.com 2>&1) || true
    exit_code=$?

    if echo "$output" | grep -q "You've successfully authenticated"; then
        echo "[OK] GitHub SSH authentication successful"
        return 0
    elif echo "$output" | grep -q "Permission denied"; then
        echo "[FAIL] GitHub SSH authentication failed"
        echo "  $output"
        return 1
    else
        echo "[WARN] Unexpected response"
        echo "  $output"
        echo "  Exit code: $exit_code"
        # GitHub returns exit code 1 even on success, so don't fail on unexpected
        if [ $exit_code -eq 1 ] && echo "$output" | grep -qi "hello\|welcome\|authenticated"; then
            echo "[OK] Appears successful (exit 1 is expected)"
            return 0
        fi
        return 1
    fi
}

verify_github_ssh "${1:-}"
