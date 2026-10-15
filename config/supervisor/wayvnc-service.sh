#!/usr/bin/env bash
set -eu

. /etc/code-docker-blender/wait-for-wayland.sh
. /etc/code-docker-blender/resolve-bind-alias.sh
wait_for_wayland_socket

VNC_PORT="${VNC_PORT:-5900}"
VNC_BIND_ALIAS="${VNC_BIND_ALIAS:-}"

# Fail-closed binding to the VNC network only. That network is shared with
# code-docker-router alone, which relays it to a person. Agents see the screen through
# the MCP's own screenshot tool (behind the token, mcp-gate-service.sh), never by
# reaching this port.
if [[ -z "${VNC_BIND_ALIAS}" ]]; then
  echo "[wayvnc-service] FATAL: VNC_BIND_ALIAS is unset - refusing to bind 0.0.0.0, which would put the screen on code-docker-internal too." >&2
  exit 1
fi
BIND_ADDR="$(resolve_bind_alias "${VNC_BIND_ALIAS}")"

# No password by default. The VNC network is internal: true and shared only with router,
# and router fronts it with its own auth (tinyauth) - the same posture
# roblox-studio-docker and code-docker-chrome settled on. Set BLENDER_VNC_PASSWORD (passed
# in as VNC_PASSWORD) to add wayvnc-level auth anyway.
WAYVNC_ARGS=(--output=HEADLESS-1 "${BIND_ADDR}" "${VNC_PORT}")
if [[ -n "${VNC_PASSWORD:-}" ]]; then
  WAYVNC_KEYDIR="${HOME}/.config/wayvnc"
  mkdir -p "${WAYVNC_KEYDIR}"
  RSA_KEY="${WAYVNC_KEYDIR}/rsa_key.pem"
  TLS_KEY="${WAYVNC_KEYDIR}/tls_key.pem"
  TLS_CERT="${WAYVNC_KEYDIR}/tls_cert.pem"
  [[ -f "${RSA_KEY}" ]] || ssh-keygen -m pem -f "${RSA_KEY}" -t rsa -N "" -q
  if [[ ! -f "${TLS_KEY}" || ! -f "${TLS_CERT}" ]]; then
    openssl req -x509 -newkey rsa:2048 -keyout "${TLS_KEY}" -out "${TLS_CERT}" \
      -days 3650 -nodes -subj "/CN=code-docker-blender" 2>/dev/null
  fi
  chmod 600 "${RSA_KEY}" "${TLS_KEY}"
  WAYVNC_CFG="/tmp/wayvnc.cfg"
  {
    echo "enable_auth=true"
    echo "username=blender"
    echo "password=${VNC_PASSWORD}"
    echo "rsa_private_key_file=${RSA_KEY}"
    echo "private_key_file=${TLS_KEY}"
    echo "certificate_file=${TLS_CERT}"
  } > "${WAYVNC_CFG}"
  chmod 600 "${WAYVNC_CFG}"
  WAYVNC_ARGS=(-C "${WAYVNC_CFG}" "${WAYVNC_ARGS[@]}")
fi

echo "[wayvnc-service] starting wayvnc on ${BIND_ADDR}:${VNC_PORT}"
exec wayvnc "${WAYVNC_ARGS[@]}"
