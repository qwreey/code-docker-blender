FROM archlinux

# Arch partial upgrades break glibc-linked binaries - always -Syu.
#
# Blender itself comes from blender.org's tarball below, not this list: Arch's package
# drags in oneAPI, OIDN, clang and friends (a ~9.5GB image, measured) and floats with the
# rolling release. These are the desktop around it and the libraries the tarball expects
# from the system (Wayland/X11 client libs, Mesa's GL/EGL, libdecor for window decorations).
# No CJK/Noto fonts: Blender draws its UI with the fonts it bundles, CJK included.
# ttf-dejavu is for labwc's titlebars on Blender's dialog windows.
RUN pacman -Syu --noconfirm --needed \
      labwc \
      wlr-randr \
      wayvnc \
      supervisor \
      caddy \
      python \
      bash \
      procps-ng \
      iproute2 \
      curl \
      openssl \
      openssh \
      xz \
      mesa \
      libglvnd \
      libxkbcommon \
      wayland \
      libdecor \
      libx11 \
      libxi \
      libxxf86vm \
      libxfixes \
      libxrender \
      libsm \
      ttf-dejavu \
    && pacman -Scc --noconfirm \
    && rm -rf /var/cache/pacman/pkg/*

# Pinned by version and checksum (blender.org publishes blender-<ver>.sha256 next to the
# release). An LTS line, so a bump is a deliberate step rather than whatever is newest.
ARG BLENDER_VERSION=5.2.2
ARG BLENDER_SHA256=84098912789dc450e95697c4184fb8a90acbe5111c2ba4aede3fecb57806a168
RUN curl -fsSL "https://download.blender.org/release/Blender${BLENDER_VERSION%.*}/blender-${BLENDER_VERSION}-linux-x64.tar.xz" -o /tmp/blender.tar.xz \
    && echo "${BLENDER_SHA256}  /tmp/blender.tar.xz" | sha256sum -c - \
    && mkdir -p /opt/blender \
    && tar -xJf /tmp/blender.tar.xz -C /opt/blender --strip-components=1 \
    && rm /tmp/blender.tar.xz \
    && ln -s /opt/blender/blender /usr/local/bin/blender \
    && blender --version | head -1

# The official MCP from Blender Lab (GPL-3.0-or-later), pinned by commit. One checkout,
# two halves: the add-on goes into Blender, the server (blmcp) into its own venv.
ARG BLMCP_COMMIT=dbbf836ad4b1025f14a2b3b504c43903f39e0b04
ADD https://projects.blender.org/lab/blender_mcp.git#${BLMCP_COMMIT} /opt/blender_mcp
# mcp pinned too: blmcp only says >=1.2,<2, and this is the version it was tested with.
ARG MCP_SDK_VERSION=1.30.0
COPY config/blender/build-prefs.py /tmp/build-prefs.py
RUN cd /opt/blender_mcp/addon \
    && python -m zipfile -c /tmp/mcp.zip blender_mcp_addon/ \
    && blender -b --online-mode --command extension install-file -r user_default --enable /tmp/mcp.zip \
    && blender -b --python /tmp/build-prefs.py 2>&1 | tee /tmp/build-prefs.log \
    && grep -q '^build-prefs: saved' /tmp/build-prefs.log \
    && rm /tmp/mcp.zip /tmp/build-prefs.py /tmp/build-prefs.log \
    && python -m venv /opt/blmcp \
    && /opt/blmcp/bin/pip install --no-cache-dir "mcp==${MCP_SDK_VERSION}" /opt/blender_mcp/mcp

# Per-program rotated log dirs, matching the stdout_logfile paths in supervisord.d/.
RUN mkdir -p /var/log/labwc /var/log/wayvnc /var/log/blender /var/log/mcp-server \
      /var/log/mcp-gate /var/log/critical-watchdog

# The config tree flattens into /etc/code-docker-blender/ the way code-docker-chrome's
# does, so service scripts reference stable paths.
COPY config/supervisord.conf /etc/code-docker-blender/supervisord.conf
COPY config/supervisord.d/ /etc/code-docker-blender/supervisord.d/
COPY config/supervisor/ /etc/code-docker-blender/
COPY config/mcp/ /etc/code-docker-blender/
# /etc/xdg/labwc/ specifically: labwc reads only $XDG_CONFIG_HOME/labwc/,
# $HOME/.config/labwc/ and /etc/xdg/labwc/, and labwc-service.sh execs it with no -C.
COPY config/wm/labwc-rc.xml /etc/xdg/labwc/rc.xml
COPY config/wm/labwc-menu.xml /etc/xdg/labwc/menu.xml

COPY entrypoint.sh /etc/code-docker-blender/entrypoint.sh
RUN chmod +x /etc/code-docker-blender/entrypoint.sh /etc/code-docker-blender/*-service.sh

ENV HOME=/root \
    XDG_CONFIG_HOME=/root/.config

ENTRYPOINT ["/etc/code-docker-blender/entrypoint.sh"]
