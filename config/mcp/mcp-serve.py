# Runs the official Blender MCP server (blmcp) unchanged, with this deployment's notice
# put in front of the instructions it sends clients at connect time.
#
# blmcp's own instructions assume the server, Blender and the agent share one machine
# (e.g. "read the bundled RST docs with grep"). Here the server and Blender are in this
# container and the agent is in code-docker, so the agent needs to be told what differs.
#
# In front, not appended: Claude Code truncates long server instructions, and blmcp's run
# past the cut on their own (measured - an appended notice never reached the model).
# blmcp's guidance is kept after it, so a version bump still lands.
import os
import sys

from mcp.server.fastmcp import FastMCP

NOTICE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mcp-notice.md")
WORK_DIR = os.environ.get("BLENDER_WORK_DIR", "/code/blender")

with open(NOTICE_PATH, encoding="utf-8") as fh:
    NOTICE = fh.read().replace("{WORK_DIR}", WORK_DIR)

_orig_init = FastMCP.__init__


def _init_with_notice(self, *args, instructions=None, **kwargs):  # type: ignore[no-untyped-def]
    _orig_init(self, *args, instructions=NOTICE + "\n" + (instructions or ""), **kwargs)


# Patched on the class, before blmcp is imported: blmcp does
# `from mcp.server.fastmcp import FastMCP` at import time, which binds this same class.
FastMCP.__init__ = _init_with_notice  # type: ignore[method-assign]

from blmcp import main  # noqa: E402

sys.exit(main())
