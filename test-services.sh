#!/bin/sh
# Copyright 2026 Thallium Solutions di Busconi Alessandro.
# SPDX-License-Identifier: Apache-2.0
set -eu

ROOT=$(CDPATH= cd "$(dirname "$0")" && pwd)
STARTED=""
WAIT_PID=""

usage() {
    cat <<'EOF'
Usage:
  sh test-services.sh

Starts the two Memcached fixtures used by the @lam/memcached integration tests:
  localhost:11211  unauthenticated fixture
  localhost:11212  auth-path fixture (memuser / mempass123)

Containers started by this invocation are stopped when the script exits.
Already-running services and containers are reused and are never stopped.
EOF
}

case "${1:-}" in
    -h|--help)
        usage
        exit 0
        ;;
    "")
        ;;
    *)
        usage >&2
        exit 2
        ;;
esac

require_command() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "error: $1 is not installed or not on PATH" >&2
        exit 1
    fi
}

container_exists() {
    docker container inspect "$1" >/dev/null 2>&1
}

container_running() {
    [ "$(docker container inspect -f '{{.State.Running}}' "$1" 2>/dev/null || true)" = "true" ]
}

port_ready() {
    python3 - "$1" "$2" <<'PY'
import socket
import sys

try:
    with socket.create_connection((sys.argv[1], int(sys.argv[2])), timeout=0.5):
        pass
except OSError:
    raise SystemExit(1)
PY
}

wait_for_port() {
    label=$1
    host=$2
    port=$3
    attempts=30

    while [ "$attempts" -gt 0 ]; do
        if port_ready "$host" "$port"; then
            echo "[test-services] $label is ready at $host:$port"
            return 0
        fi
        attempts=$((attempts - 1))
        sleep 1
    done

    echo "error: $label did not become ready at $host:$port within 30 seconds" >&2
    return 1
}

start_service() {
    name=$1
    port=$2
    shift 2

    if port_ready localhost "$port"; then
        echo "[test-services] localhost:$port already accepts connections; leaving it untouched"
        return 0
    fi

    if container_exists "$name"; then
        if ! container_running "$name"; then
            echo "error: container $name exists but is stopped; remove or start it before retrying" >&2
            return 1
        fi
        echo "[test-services] $name is already running; leaving it running"
    else
        echo "[test-services] starting $name"
        docker run --rm -d --name "$name" "$@" >/dev/null
        STARTED="$STARTED $name"
    fi

    wait_for_port "$name" localhost "$port"
}

cleanup() {
    status=$?
    trap - EXIT INT TERM
    if [ -n "$WAIT_PID" ]; then
        kill "$WAIT_PID" >/dev/null 2>&1 || true
        WAIT_PID=""
    fi
    if [ -n "$STARTED" ]; then
        echo
        echo "[test-services] stopping only containers started by this invocation:$STARTED"
        for name in $STARTED; do
            docker stop "$name" >/dev/null 2>&1 || true
        done
    fi
    exit "$status"
}

require_command docker
require_command python3
if ! docker info >/dev/null 2>&1; then
    echo "error: Docker is installed, but the daemon is unavailable or inaccessible" >&2
    exit 1
fi

trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

start_service memcached-test 11211 \
    -p 11211:11211 \
    memcached:latest

start_service memcached-test-auth 11212 \
    -p 11212:11211 \
    -e MEMCACHED_USERNAME=memuser \
    -e MEMCACHED_PASSWORD=mempass123 \
    memcached:1.6

cat <<EOF

[test-services] Memcached fixtures are ready.
[test-services] In another terminal, run:

  cd "$ROOT"
  python3 tests/run_memcached_tests.py --verbose --require-services

[test-services] Press Ctrl-C here to stop containers started by this script.
EOF

while :; do
    sleep 3600 &
    WAIT_PID=$!
    wait "$WAIT_PID"
    WAIT_PID=""
done
