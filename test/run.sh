#!/usr/bin/env bash
# End-to-end check of code-docker-blender.yml against a stub stack (compose.test.yml).
# Builds, starts, runs check.py from the stub code-docker, probes the network boundaries,
# and tears everything down (volumes included) unless KEEP=1.
set -euo pipefail
cd "$(dirname "$0")"

export PREFIX="${PREFIX:-bltest-}"
export BLENDER_MCP_TOKEN="test-$(head -c 16 /dev/urandom | od -An -tx1 | tr -d ' \n')"
dc() { docker compose -p "${PREFIX%-}" -f compose.test.yml "$@"; }

cleanup() { [[ "${KEEP:-0}" == 1 ]] || dc down -v --remove-orphans >/dev/null 2>&1 || true; }
trap cleanup EXIT

dc up -d --build
fail=0
check() { if "$@"; then echo "  ok   $*"; else echo "  FAIL $*"; fail=1; fi; }

echo "== waiting for the MCP gate"
for _ in $(seq 60); do
  dc exec -T code-docker python -c "import httpx,sys; sys.exit(0 if httpx.post('http://blender:8765/').status_code == 401 else 1)" 2>/dev/null && break
  sleep 2
done

echo "== MCP over the gate (check.py)"
dc exec -T -e BLENDER_MCP_TOKEN code-docker python /test/check.py || fail=1

echo "== network boundaries"
# reaches <service> <host> <port>: 0 if a TCP connection opens. Both stub images have
# a different toolbox (busybox nc vs python), so try each.
reaches() {
  dc exec -T "$1" sh -c "nc -z -w 2 $2 $3 2>/dev/null || python -c \"import socket; socket.create_connection(('$2', $3), 2)\" 2>/dev/null" >/dev/null 2>&1
}
refused() { ! reaches "$@"; }
unresolvable() { ! dc exec -T "$1" getent hosts "$2" >/dev/null 2>&1; }
rfb_banner() { dc exec -T code-docker-router sh -c 'nc -w 3 blender-vnc 5900 </dev/null | head -c 3' | grep -q RFB; }
no_default_route() { ! dc exec -T code-docker-blender ip route show default | grep -q .; }

check reaches code-docker blender 8765
check refused code-docker blender 9876   # add-on socket: loopback only
check refused code-docker blender 8000   # blmcp: loopback only
check refused code-docker blender 5900   # VNC: not bound on code-docker-internal
check unresolvable code-docker blender-vnc
check rfb_banner
check refused code-docker-router blender-vnc 8765   # MCP gate: not on the VNC network
check no_default_route

echo "== startup guards"
gate_refuses_empty_token() {
  # Captured first: under pipefail the script's own (expected) exit 1 would fail the pipe.
  local out
  out="$(dc exec -T -e BLENDER_MCP_TOKEN= code-docker-blender /etc/code-docker-blender/mcp-gate-service.sh 2>&1)" && return 1
  grep -q FATAL <<<"${out}"
}
check gate_refuses_empty_token

exit "${fail}"
