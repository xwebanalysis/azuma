#!/usr/bin/env bash
set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

MODE=""
COMPOSE=""

usage() {
    echo "Usage: ./azuma.sh [docker|local] [backend|frontend|all]"
    echo ""
    echo "Modes:"
    echo "  docker   Run the full stack with Docker Compose"
    echo "  local    Run backend and frontend natively"
    exit 1
}

find_compose() {
    if docker compose version &>/dev/null; then
        COMPOSE="docker compose"
    elif command -v docker-compose &>/dev/null; then
        COMPOSE="docker-compose"
    else
        echo -e "${RED}Docker Compose not found. Install Docker or use local mode.${NC}"
        exit 1
    fi
}

run_docker() {
    find_compose
    case "${2:-all}" in
        backend)
            $COMPOSE -f "$ROOT_DIR/docker-compose.yml" up --build backend
            ;;
        frontend)
            $COMPOSE -f "$ROOT_DIR/docker-compose.yml" up --build frontend
            ;;
        all)
            $COMPOSE -f "$ROOT_DIR/docker-compose.yml" up --build
            ;;
        *)
            usage
            ;;
    esac
}

run_local_backend() {
    cd "$ROOT_DIR/backend"
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    export DB_DRIVER=sqlite
    export DB_PATH=./azuma.db
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
}

run_local_frontend() {
    cd "$ROOT_DIR/frontend"
    npm install
    npm start
}

run_local() {
    case "${2:-all}" in
        backend)
            run_local_backend
            ;;
        frontend)
            run_local_frontend
            ;;
        all)
            run_local_backend &
            run_local_frontend
            ;;
        *)
            usage
            ;;
    esac
}

case "$1" in
    docker)
        run_docker "$@"
        ;;
    local)
        run_local "$@"
        ;;
    *)
        usage
        ;;
esac
