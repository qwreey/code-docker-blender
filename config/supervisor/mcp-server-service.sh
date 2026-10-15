#!/usr/bin/env bash
set -eu

# blmcp relays each tool call to the Blender add-on's socket, which listens on loopback
# only (blender-service.sh). These are blmcp's own variable names for that connection.
export BLENDER_MCP_HOST=localhost
export BLENDER_MCP_PORT=9876

# Loopback as well: blmcp's HTTP transport has no auth and answers CORS for any origin.
# mcp-gate (Caddy) is the only thing that reaches it, and Caddy is what checks the token.
exec /opt/blmcp/bin/python /etc/code-docker-blender/mcp-serve.py \
  --transport http --host 127.0.0.1 --port 8000
