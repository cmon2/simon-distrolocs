#!/bin/bash
# verify_forgejo_token_auth.sh - Verify token authentication to Forgejo
# Usage: verify_forgejo_token_auth.sh [forgejo_base] [token_path]
#   forgejo_base: Forgejo URL (e.g., http://localhost:3000)
#   token_path: Path to token file (optional, auto-detected)
#
# Exits: 0 on success, 1 on failure

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SIMON_IDE_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

verify_forgejo_token() {
    local forgejo_base="${1:-}"
    local token_path="${2:-}"
    
    echo "Verifying Forgejo token authentication..."
    echo ""
    
    # Auto-detect forgejo_base from git remotes if not provided
    if [ -z "$forgejo_base" ]; then
        local remote_url
        remote_url=$(git remote get-url origin 2>/dev/null || true)
        if [ -n "$remote_url" ]; then
            # Extract host from URL like http://192.168.56.1:3000/simon/repo.git
            if [[ "$remote_url" =~ ^(https?://[^/]+) ]]; then
                forgejo_base="${BASH_REMATCH[1]}"
            fi
        fi
    fi
    
    if [ -z "$forgejo_base" ]; then
        echo -e "${RED}[ERROR] Forgejo base URL not provided and could not auto-detect${NC}"
        return 1
    fi
    
    echo "  Forgejo: $forgejo_base"
    
    # Auto-detect token path if not provided
    if [ -z "$token_path" ]; then
        if [ -f "$SIMON_IDE_DIR/02_configs/git/Forgejo/token" ]; then
            token_path="$SIMON_IDE_DIR/02_configs/git/Forgejo/token"
        else
            echo -e "${RED}[ERROR] No token file found for Forgejo${NC}"
            echo "Expected at: $SIMON_IDE_DIR/02_configs/git/Forgejo/token"
            return 1
        fi
    fi
    
    echo "  Token file: $token_path"
    
    if [ ! -f "$token_path" ]; then
        echo -e "${RED}[ERROR] Token file not found: $token_path${NC}"
        return 1
    fi
    
    # Read token (handle URL format)
    local token
    token=$(cat "$token_path" | tr -d '\n')
    
    # Handle URL-formatted tokens
    if [[ "$token" == *"@"* ]] && [[ "$token" == *"://"* ]]; then
        # Extract token from URL format: scheme://user:token@host
        token=$(echo "$token" | sed -n 's/.*:\/\/[^:]*:\([^@]*\)@.*/\1/p')
    fi
    
    # Test API access
    echo "  Testing API access to ${forgejo_base}/api/v1/user..."
    
    local response
    local http_code
    
    response=$(curl -s -w "\n%{http_code}" -H "Authorization: Bearer $token" "${forgejo_base}/api/v1/user" 2>&1)
    http_code=$(echo "$response" | tail -n1)
    response=$(echo "$response" | sed '$d')
    
    if [ "$http_code" = "200" ]; then
        local login
        login=$(echo "$response" | grep -o '"login":"[^"]*"' | head -1 | cut -d'"' -f4)
        echo -e "${GREEN}[OK] Forgejo token authentication successful${NC}"
        echo "  Logged in as: $login"
        return 0
    elif [ "$http_code" = "401" ]; then
        echo -e "${RED}[FAIL] Forgejo token authentication failed (401 Unauthorized)${NC}"
        return 1
    else
        echo -e "${RED}[FAIL] Forgejo API returned HTTP $http_code${NC}"
        echo "  Response: $response"
        return 1
    fi
}

verify_forgejo_token "${1:-}" "${2:-}"
