# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A **provider**: a container that attaches a GUI Blender to
[code-docker](https://github.com/qwreey/code-docker). Infrastructure/config only
(Dockerfile, compose overlay, shell service scripts, one small Python launcher).

One Blender session is reachable two ways at once: an agent in code-docker drives it
through the official Blender Lab MCP, and a person watches and edits the same session over
VNC. The agent sees the screen through the MCP's own screenshot tool and judges models by
rendering them to PNGs in the shared directory.

The design follows code-docker-chrome (overlay-only, labwc + wayvnc, fail-closed binds,
critical-watchdog). Where this repo differs from it, the reason is below.

## Architecture

```
[code-docker]                                  [code-docker-blender]
claude ── HTTP + Bearer ──▶ blender:8765 ──▶ mcp-gate (Caddy, checks token)
                              (code-docker-internal)     │
                                                         ▼
                                              mcp-server (blmcp, 127.0.0.1:8000)
                                                         │ TCP, loopback
                                                         ▼
                                              Blender GUI + MCP add-on (localhost:9876)
                                                         │
/code/blender ◀──── blender-work volume ────▶ /code/blender (TMPDIR=/code/blender/.tmp)
                                                         │
person ◀── router VNC tab ◀── blender-vnc:5900 ◀──── wayvnc ◀── labwc (GPU via /dev/dri)
```

### The MCP runs here, not in code-docker

blmcp has a stdio mode meant to run next to the client, and an HTTP mode. It runs here in
HTTP mode, behind a token:

- code-docker needs nothing installed. Its whole side is one `claude mcp add` with a
  header. There is no installer to re-run and no Python or uv in the agent container.
- The add-on's socket (no auth, arbitrary Python) stays on loopback. Exposing it to
  code-docker instead would have needed either a dedicated network that code-docker joins,
  or a wrap/unwrap pair like cdp-bridge. The first is what code-docker-chrome rejected (a
  provider must not edit the main project's topology). The second means a daemon in
  code-docker.
- Cost: blmcp's instructions assume a shared filesystem, e.g. "grep the bundled RST
  docs". `config/mcp/mcp-serve.py` puts a notice (`mcp-notice.md`) in front of them.
  - **It must go in front and stay short.** Claude Code truncates long server instructions
    (measured with the real CLI: blmcp's ~6KB are cut partway, and an appended notice never
    reached the model).
  - Keep `mcp-notice.md` under ~1.5KB and put the most important lines first.

### Networks

| Network | Members | Shape |
|---|---|---|
| `code-docker-internal` | Blender (alias `blender`), code-docker, dind, router, … | Only the token-gated MCP port listens here |
| `blender-vnc` (`internal: true`) | Blender (alias `blender-vnc`), router | Screen to a person |

- **Blender is directly on code-docker-internal**, unlike Chrome and Roblox Studio, which
  sit on their own networks behind a front container.
  - Those two run content from the internet (any site's JavaScript, a game's HttpService).
  - Blender runs only what the agent sends and what the person at VNC does. Both already
    reach everything on code-docker-internal from code-docker.
  - It has no internet to fetch anything else (next point).
  - **If this container ever gets egress, revisit this.** A downloaded add-on or a .blend
    with scripts would then run beside code-docker's nginx and dind's API.
- **No egress, on purpose.** There is no `netinit.provider` label on the container, so
  code-docker's netinit-docker never plants a default route. That is also why
  `entrypoint.sh` has no `NETINIT_WAIT` and no dns-local: Docker's `127.0.0.11` answers the
  only names it needs.
  - Adding egress means that label plus code-docker-chrome's
    `NETINIT_WAIT`/`DNS_LOCAL_ENABLED` pieces.
- **Listeners bind one network each and fail closed**
  (`config/supervisor/resolve-bind-alias.sh`):
  - mcp-gate binds `MCP_BIND_NAME`, a network-qualified `<container>.<network>` name, so
    it can't resolve to the VNC-side address.
  - wayvnc binds `blender-vnc`.
  - The add-on and blmcp bind loopback.
  - `test/run.sh` checks every one of these from both sides.
- `blender-vnc` carries `netinit.provider` + `netinit.exempt-forward` and no gateway, the
  same as code-docker-chrome's `chrome-vnc`.

### The shared directory

`blender-work` is mounted at `${BLENDER_WORK_DIR:-/code/blender}` in **both** containers,
at the same path. That is what makes a path the MCP returns a path the agent can open.

- `blender-service.sh` sets `TMPDIR` to `<work dir>/.tmp`. blmcp's `render_*_to_path` tools
  keep only the basename of the path they're given and always write under
  `bpy.app.tempdir`. Without this, they would return paths that exist only in this
  container. Autosaves go there too.
- Inside code-docker it is a nested mount over the `/code` bind. dind mounts the same
  HOME_VOLUME at `/code` and sees an empty directory there.

### GPU

`/dev/dri` is passed through. EEVEE, Workbench and the viewport render on it, and so does
labwc: `entrypoint.sh` does not force `WLR_RENDERER=pixman` the way code-docker-chrome
does.

Measured on a Radeon 780M:
- EEVEE at 960x540 takes about 2s, versus about 13s on llvmpipe.
- An idle GUI costs about 1% CPU and about 700MB RAM, with no measurable GPU or power
  change.

Only Mesa drivers are installed; NVIDIA's proprietary stack is not covered. Cycles HIP on
gfx1103 is not supported upstream, so Cycles is CPU-only here.

## Blender and the add-on

- **Blender comes from blender.org's tarball**, pinned by version and sha256
  (`BLENDER_VERSION`/`BLENDER_SHA256` in the Dockerfile). Arch's `blender` package was
  rejected: it pulls in oneAPI, OIDN, clang and more (a ~9.5GB image, measured) and floats
  with the rolling release.
  - To bump, take the hash from `https://download.blender.org/release/Blender<X.Y>/blender-<ver>.sha256`.
- **The MCP is pinned by commit** (`BLMCP_COMMIT`), and so is the `mcp` SDK
  (`MCP_SDK_VERSION`). blmcp only says `>=1.2,<2`. One checkout serves both halves: the
  add-on is zipped and installed into Blender, and blmcp is pip-installed into
  `/opt/blmcp`.
- **`--online-mode` is required.** The add-on refuses to open its socket without it. It
  also makes Blender try the Online Essentials asset library and extensions.blender.org
  sync, which only fail here. `config/blender/build-prefs.py` turns both off and also
  disables the splash screen, which otherwise covers every screenshot.
  - Those preferences are saved into the image's `userpref.blend`, so GUI changes a person
    makes do not survive a recreate.
  - `build-prefs.py` also asserts the add-on is enabled with its default `localhost`
    auto-start, so a renamed add-on fails the build.
- The add-on's own defaults are the configuration: auto-start, `localhost:9876`. Nothing
  sets them at runtime.

## Process supervision

The same split as code-docker-chrome:

- `entrypoint.sh` does the once-only setup and `exec`s supervisord.
- Each program has one `[program:...]` file in `config/supervisord.d/`, with its script in
  `config/supervisor/`. That directory flattens into `/etc/code-docker-blender/`.
- `labwc` and `wayvnc` are `autorestart=false` + `startretries=0` and are watched by
  `critical-watchdog`, which stops the container if either dies.
- **`blender`, `mcp-server` and `mcp-gate` are deliberately not watched.**
  - Quitting Blender is ordinary for a person at VNC, and `autorestart=true` brings it
    back. The add-on auto-starts again and blmcp reconnects on the next call (measured).
  - The scene does not survive; that is why the notice tells agents to save.
- The labwc root menu replaces the built-in one, whose "Exit" would stop labwc and so the
  container. It offers "Start Blender".
- The labwc window rule maximizes anything whose app_id matches `*blender*` and drops its
  server-side titlebar, since Blender draws its own top bar.

## Integration with code-docker

Attached through `ootb-manifest.env`: ootb/migrate writes `extra-include.yml`, adds
`blender-vnc` to router's allowed target hosts, and generates `BLENDER_MCP_TOKEN`.

The overlay merges into services it does not define:

- **`code-docker`** gets the token in its environment, the shared volume, and this repo's
  `code-docker/` directory read-only at `/run/code-docker-blender/`. That directory holds
  the subagent template `blender-modeler.md`, which people copy into `~/.claude/agents/`.
- **`code-docker-router`** joins `blender-vnc`. The VNC tab entry (`rfb`,
  `blender-vnc:5900`) is added at runtime from router-manager.

## Testing

`test/run.sh` brings up `test/compose.test.yml`, a stub stack, under `PREFIX=bltest-`:
- a stub `code-docker` (Python + the mcp SDK);
- a stub `code-docker-router` (busybox);
- the real overlay.

It then checks:
- the gate's 401s;
- the deployment notice;
- the tool list;
- a model built, rendered with EEVEE on the GPU and exported, read back from the
  code-docker side;
- `render_thumbnail_to_path`'s returned path;
- a window screenshot;
- every network boundary;
- the empty-token startup guard.

It tears down with `-v` unless `KEEP=1`.

Not covered by it:
- The real code-docker stack. `docker compose config` against it merges cleanly.
- router's VNC tab.

Claude Code itself was checked once by hand against the stub stack through a temporary
loopback relay: tools, an image result, and a 401 on a wrong token.

## Conventions

These match code-docker-chrome:
- Service scripts are `#!/usr/bin/env bash` + `set -eu` and `exec` their long-running
  program last.
- Shared helpers are sourced, not executed.
- Comments carry the *why*, and most of them record something that was measured.
