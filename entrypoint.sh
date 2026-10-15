#!/usr/bin/env bash
set -euo pipefail

# Everything past the exec at the bottom is supervisord's job (config/supervisord.conf
# + config/supervisord.d/*.conf). This script only does what must happen once, before
# any program starts.
#
# No NETINIT_WAIT and no dns-local, unlike code-docker-chrome: this container never gets
# a default route (it carries no netinit.provider label - see code-docker-blender.yml),
# so there is nothing to wait for, and the only names it needs are on its own networks,
# which Docker's 127.0.0.11 answers.

export HOME="${HOME:-/root}"
export XDG_RUNTIME_DIR="/tmp/xdg-runtime"

# `docker restart` reuses the writable layer, so a stale wayland-N socket from a
# previously crashed labwc survives here and would satisfy wait-for-wayland.sh's
# existence check instantly - before the new labwc has made its own socket. Wipe it so
# only a live socket is findable.
rm -rf "${XDG_RUNTIME_DIR}"
mkdir -p "${XDG_RUNTIME_DIR}"
chmod 700 "${XDG_RUNTIME_DIR}"

# No WLR_RENDERER override (code-docker-chrome forces pixman): with /dev/dri passed in,
# wlroots picks the GPU, and Blender's viewport renders there too.
export WLR_BACKENDS=headless
export WLR_LIBINPUT_NO_DEVICES=1

echo "[entrypoint] handing off to supervisord"
exec supervisord -n -c /etc/code-docker-blender/supervisord.conf
