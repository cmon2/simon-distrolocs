#!/bin/bash
# verify_gitlab_token_auth.sh - Verify token authentication to GitLab
# Usage: verify_gitlab_token_auth.sh [gitlab_api_url] [token_path]
#   gitlab_api_url: GitLab API URL (e.g., https://gitlab.com)
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

verify_gitlab_token() {
    local gitlab_api="${1:-}"
    local token_path="${2:-}"
    
    echo "Verifying GitLab token authentication..."
    echo ""
    
    # Default GitLab API URL
    if [ -z "$gitlab_api" ]; then
        gitlab_api="https://gitlab.com"
    fi
    
    echo "  GitLab API: $gitlab_api"
    
    # Auto-detect token path if not provided
    if [ -z "$token_path" ]; then
        if [ -f "$SIMON_IDE_DIR/02_configs/git/Gitlab/token" ]; then
            token_path="$SIMON_IDE_DIR/02_configs/git/Gitlab/token"
        elif [ -f "$SIMON_IDE_DIR/02_configs/git/Gitlab/gitlab_key" ]; then
            token_path="$SIMON_IDE_DIR/02_configs/git/Gitlab/gitlab_key"
        else
            echo -e "${RED}[ERROR] No token file found for GitLab${NC}"
            echo "Expected at: $SIMON_IDE_DIR/02_configs/git/Gitlab/token"
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
        # Extract token from URL format
        token=$(echo "$token" | sed -n 's/.*:\/\/[^:]*:\([^@]*\)@.*/\1/p')
    fi
    
    # Test API access
    echo "  Testing API access to ${gitlab_api}/api/v4/user..."
    
    local response
    local http_code
    
    response=$(curl -s -w "\n%{http_code}" -H "PRIVATE-TOKEN: $token" "${gitlab_api}/api/v4/user" 2>&1)
    http_code=$(echo "$response" | tail -n1)
    response=$(echo "$response" | sed '$d')
    
    if [ "$http_code" = "200" ]; then
        local username
        username=$(echo "$response" | grep -o '"username":"[^"]*"' | head -1 | cut -d'"' -f4)
        echo -e "${GREEN}[OK] GitLab token authentication successful${NC}"
        echo "  Logged in as: $username"
        return 0
    elif [ "$http_code" = "401" ]; then
        echo -e "${RED}[FAIL] GitLab token authentication failed (401 Unauthorized)${NC}"
        return 1
    else
        echo -e "${RED}[FAIL] GitLab API returned HTTP $http_code${NC}"
        echo "  Response: $response"
        return 1
    fi
}

verify_gitlab_token "${1:-}" "${2:-}"
