# MCP checks, run from the stub code-docker by run.sh: the gate's auth, then what an
# agent actually does - build a model, render it, export it, look at the window - and
# that every path the server hands back is readable from this side.
import asyncio
import base64
import os
import sys

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

URL = "http://blender:8765/"
TOKEN = os.environ["BLENDER_MCP_TOKEN"]
WORK = os.environ.get("BLENDER_WORK_DIR", "/code/blender")
failed = False


def check(ok: bool, what: str) -> None:
    global failed
    print(("  ok   " if ok else "  FAIL ") + what)
    failed |= not ok


MODEL = f"""
import bpy, math, mathutils
bpy.ops.scene.new(type="EMPTY")
sc = bpy.context.scene
sc.name = "check"
bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.18, depth=1.0, location=(0, 0, 0.5))
for r, z in ((1.0, 1.3), (0.8, 1.9), (0.55, 2.45)):
    bpy.ops.mesh.primitive_cone_add(vertices=8, radius1=r, depth=0.9, location=(0, 0, z))
bpy.ops.object.camera_add(location=(5.5, -5.5, 3.5))
cam = bpy.context.object
cam.rotation_euler = (mathutils.Vector((0, 0, 1.3)) - cam.location).to_track_quat("-Z", "Y").to_euler()
sc.camera = cam
bpy.ops.object.light_add(type="SUN", location=(0, 0, 6))
sc.render.engine = "BLENDER_EEVEE"
sc.render.resolution_x, sc.render.resolution_y = 640, 480
sc.render.filepath = "{WORK}/check-eevee.png"
bpy.ops.render.render(write_still=True)
bpy.ops.object.select_all(action="SELECT")
bpy.ops.export_scene.gltf(filepath="{WORK}/check.glb", use_selection=True)
import gpu
print("renderer:", gpu.platform.renderer_get())
"""

WINDOWS = "import bpy; print('windows:', len(bpy.context.window_manager.windows))"

# For run.sh's VNC input check: the main window's 3D view orientation.
VIEW = """
import bpy
a = next(a for a in bpy.context.window_manager.windows[0].screen.areas if a.type == 'VIEW_3D')
print('view:', tuple(round(v, 4) for v in a.spaces.active.region_3d.view_rotation))
"""


async def view() -> None:
    auth = {"Authorization": f"Bearer {TOKEN}"}
    async with streamablehttp_client(URL, headers=auth) as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            res = await s.call_tool("execute_blender_code", {"code": VIEW})
            print(res.content[0].text.split("view: ")[1].split("\\n")[0])


async def main() -> None:
    # An empty server-side token is refused at startup instead (run.sh checks that), so
    # there is no "Bearer " case here - httpx won't even send that header.
    for headers, label in (({}, "no token"), ({"Authorization": "Bearer wrong"}, "wrong token")):
        r = httpx.post(URL, headers=headers, json={})
        check(r.status_code == 401, f"{label} -> {r.status_code}")

    auth = {"Authorization": f"Bearer {TOKEN}"}
    async with streamablehttp_client(URL, headers=auth) as (r, w, _):
        async with ClientSession(r, w) as s:
            init = await s.initialize()
            check("code-docker-blender" in (init.instructions or ""), "instructions carry the deployment notice")
            check(f"{WORK}/.tmp" in (init.instructions or ""), "notice has BLENDER_WORK_DIR filled in")

            # The gate answers within a second of start; Blender plus the add-on's
            # auto-start takes several more. Until then every tool reports "Cannot connect
            # to Blender" - wait it out rather than fail on a cold start.
            for _ in range(60):
                res = await s.call_tool("get_objects_summary", {})
                if res.content and '"status": "ok"' in res.content[0].text:
                    break
                await asyncio.sleep(1)
            check('"status": "ok"' in res.content[0].text, "Blender's add-on answers through blmcp")

            tools = [t.name for t in (await s.list_tools()).tools]
            check(len(tools) >= 20, f"{len(tools)} tools listed")

            res = await s.call_tool("execute_blender_code", {"code": MODEL})
            text = res.content[0].text if res.content else ""
            check('"status": "ok"' in text, "execute_blender_code: model + EEVEE render + glTF export")
            renderer = [l for l in text.split("\\n") if "renderer:" in l]
            print("       " + (renderer[0].strip() if renderer else text[:400]))
            for f in ("check-eevee.png", "check.glb"):
                check(os.path.getsize(f"{WORK}/{f}") > 1000, f"{WORK}/{f} readable from code-docker")

            res = await s.call_tool("render_thumbnail_to_path", {"output_path": "thumb.png"})
            path = res.content[0].text.split('"filepath": "')[1].split('"')[0] if res.content and "filepath" in res.content[0].text else ""
            check(path.startswith(f"{WORK}/.tmp/") and os.path.exists(path), f"render_thumbnail_to_path -> {path}")
            # The render tools render with INVOKE_DEFAULT; a Render Result window would cover
            # the person's scene (build-prefs.py sets render_display_type to prevent it).
            res = await s.call_tool("execute_blender_code", {"code": WINDOWS})
            text = res.content[0].text if res.content else ""
            check("windows: 1\\n" in text, "a render opens no window over the scene")

            res = await s.call_tool("get_screenshot_of_window_as_image", {})
            imgs = [c for c in res.content if c.type == "image"]
            check(bool(imgs), "get_screenshot_of_window_as_image returns an image")
            if imgs:
                with open(f"{WORK}/check-window.png", "wb") as fh:
                    fh.write(base64.b64decode(imgs[0].data))


if sys.argv[1:] == ["view"]:
    asyncio.run(view())
    sys.exit(0)
asyncio.run(main())
sys.exit(1 if failed else 0)
