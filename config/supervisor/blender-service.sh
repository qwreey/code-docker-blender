#!/usr/bin/env bash
set -eu

. /etc/code-docker-blender/wait-for-wayland.sh
wait_for_wayland_socket

# Blender's temp directory (bpy.app.tempdir) follows TMPDIR. The MCP's render_*_to_path
# tools ignore the directory part of the path they are given and always write under
# bpy.app.tempdir, so it has to be on the volume code-docker mounts at the same path -
# otherwise the agent gets back a path that exists only in this container. Autosaves
# (File > Recover > Auto Save) land here too, which is what makes them survive a restart.
WORK_DIR="${BLENDER_WORK_DIR:-/code/blender}"
export TMPDIR="${WORK_DIR}/.tmp"
mkdir -p "${TMPDIR}"

# Relative paths in agent code and Blender's file browser both start here.
cd "${WORK_DIR}"

# --online-mode: the MCP add-on refuses to open its socket unless Blender's online
# access is allowed. The container has no route out (see code-docker-blender.yml), so
# this permits the loopback socket and nothing more in practice.
#
# The add-on's own defaults are what we want: auto-start, bound to localhost:9876. Only
# mcp-server (same container) dials it; the port is never reachable from outside.
exec blender --online-mode
