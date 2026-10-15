#!/usr/bin/env bash
set -eu

. /etc/code-docker-blender/resolve-bind-alias.sh

# The token is the boundary: execute_blender_code runs arbitrary Python as root in this
# container, and this port sits on code-docker-internal, which dind's containers and
# other providers share. An empty token would make Caddy compare against "Bearer ", which
# any caller can send - so refuse to start rather than run open.
if [[ -z "${BLENDER_MCP_TOKEN:-}" ]]; then
  echo "[mcp-gate] FATAL: BLENDER_MCP_TOKEN is empty - run code-docker's migrate.sh (it generates one) or set it in code-docker's .env" >&2
  exit 1
fi

# Bind code-docker-internal only, never 0.0.0.0: the VNC network is shared with router,
# which has no business reaching Blender's Python. MCP_BIND_NAME is network-qualified
# (<container>.<network>) so it cannot resolve to this container's VNC-side address.
MCP_BIND_ADDR="$(resolve_bind_alias "${MCP_BIND_NAME:?MCP_BIND_NAME must be set}")"
export MCP_BIND_ADDR MCP_GATE_PORT="${MCP_GATE_PORT:-8765}" BLENDER_MCP_TOKEN

echo "[mcp-gate] listening on ${MCP_BIND_ADDR}:${MCP_GATE_PORT}"
exec caddy run --config /etc/code-docker-blender/Caddyfile --adapter caddyfile
