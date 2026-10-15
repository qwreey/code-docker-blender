"""Multi-part models ("kits") in one .blend, exported one part at a time.

Importable from execute_blender_code (`import partkit`); build-prefs.py puts its
directory on Blender's script path. The layout it assumes:

- One collection per part, named after the part.
- In it, an empty with the same name: the part's root. Every other object of the part is
  parented to it. Where the root sits is the part's origin in the exported file.
- Where the roots are placed in the scene is presentation only (a lineup to look at,
  or an assembly to fit parts against each other). export() moves the root to the world
  origin for the duration of the export, so the layout never leaks into a game file.
"""
import os

import bpy
from mathutils import Matrix, Vector

__all__ = ["new_part", "add", "parts", "lineup", "assemble", "show", "export", "export_all"]


def _object_mode() -> None:
    if bpy.context.mode != "OBJECT" and bpy.context.view_layer.objects.active:
        bpy.ops.object.mode_set(mode="OBJECT")


def _layer_collection(name: str, lc=None):
    lc = lc or bpy.context.view_layer.layer_collection
    if lc.name == name:
        return lc
    for child in lc.children:
        found = _layer_collection(name, child)
        if found:
            return found
    return None


def new_part(name: str, location=(0.0, 0.0, 0.0)):
    """Create part `name`: its collection and root empty. Makes the collection active,
    so objects added with bpy.ops land in it; parent them with add()."""
    if name in bpy.data.collections:
        raise ValueError(f"a collection named {name!r} already exists")
    col = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(col)
    root = bpy.data.objects.new(name, None)
    root.empty_display_type = "PLAIN_AXES"
    root.empty_display_size = 0.25
    root.location = location
    col.objects.link(root)
    bpy.context.view_layer.active_layer_collection = _layer_collection(name)
    return root


def add(obj, part: str) -> None:
    """Move `obj` into part `part` and parent it to the part's root, keeping where it
    is in the world."""
    col = bpy.data.collections[part]
    root = col.objects[part]
    for c in list(obj.users_collection):
        if c is not col:
            c.objects.unlink(obj)
    if obj.name not in col.objects:
        col.objects.link(obj)
    world = obj.matrix_world.copy()
    obj.parent = root
    obj.matrix_world = world


def parts() -> list[str]:
    """Names of every part in the current scene."""
    return [c.name for c in bpy.context.scene.collection.children_recursive
            if c.name in c.objects and c.objects[c.name].type == "EMPTY"]


def _bounds_in_root(name: str):
    """Min/max corner of the part's meshes, in its root's space."""
    root = bpy.data.objects[name]
    inv = root.matrix_world.inverted()
    pts = [inv @ (o.matrix_world @ Vector(c))
           for o in bpy.data.collections[name].all_objects if o.type != "EMPTY"
           for c in o.bound_box]
    if not pts:
        return Vector((0, 0, 0)), Vector((0, 0, 0))
    return (Vector([min(p[i] for p in pts) for i in range(3)]),
            Vector([max(p[i] for p in pts) for i in range(3)]))


# Where a root stood before lineup() moved it, so assemble() can put it back. Stored on
# the root, so it is saved with the .blend.
_PLACED = "partkit_placed"


def lineup(names=None, gap: float = 0.5) -> dict:
    """Place the parts' roots side by side along X, `gap` meters apart, roots at y=0 and
    z=0. Presentation only - exports don't depend on it. The arrangement it replaces
    (an assembly) is kept; assemble() restores it."""
    names = names or parts()
    x = 0.0
    placed = {}
    for n in names:
        lo, hi = _bounds_in_root(n)
        root = bpy.data.objects[n]
        if _PLACED not in root:
            root[_PLACED] = tuple(root.location)
        root.location = (x - lo.x, 0.0, 0.0)
        placed[n] = tuple(root.location)
        x += (hi.x - lo.x) + gap
    return placed


def assemble(names=None) -> None:
    """Undo lineup(): put the roots back where they were before it."""
    for n in names or parts():
        root = bpy.data.objects[n]
        if _PLACED in root:
            root.location = tuple(root[_PLACED])
            del root[_PLACED]


def show(names=None) -> None:
    """Show only `names` (default: every part) and frame them in the person's 3D view -
    what they see over VNC, and what get_screenshot_of_window_as_image captures."""
    _object_mode()
    names = names or parts()
    for n in parts():
        lc = _layer_collection(n)
        lc.exclude = False
        lc.hide_viewport = n not in names
    bpy.ops.object.select_all(action="DESELECT")
    for n in names:
        for o in bpy.data.collections[n].all_objects:
            o.hide_set(False)
            o.select_set(True)
    win = bpy.context.window_manager.windows[0]
    for area in win.screen.areas:
        if area.type == "VIEW_3D":
            region = next(r for r in area.regions if r.type == "WINDOW")
            with bpy.context.temp_override(window=win, area=area, region=region):
                bpy.ops.view3d.view_selected()
            break


def export(name: str, directory: str, fmt: str = "glb") -> str:
    """Export part `name` to `<directory>/<name>.<fmt>` (glb or fbx) with its root at the
    world origin. The scene is left as it was."""
    _object_mode()
    os.makedirs(directory, exist_ok=True)
    col = bpy.data.collections[name]
    root = col.objects[name]
    lc = _layer_collection(name)
    saved_lc = (lc.exclude, lc.hide_viewport)
    saved_root = root.matrix_world.copy()
    saved_sel = [o for o in bpy.context.view_layer.objects if o.select_get()]
    hidden = [o for o in col.all_objects if o.hide_get()]
    path = os.path.join(directory, f"{name}.{fmt}")
    try:
        lc.exclude, lc.hide_viewport = False, False
        for o in hidden:
            o.hide_set(False)
        root.matrix_world = Matrix.Identity(4)
        bpy.context.view_layer.update()
        bpy.ops.object.select_all(action="DESELECT")
        for o in col.all_objects:
            o.select_set(True)
        if fmt == "glb":
            # use_active_scene: without it the exporter walks every scene, and objects
            # left selected in another one end up in this part's file (measured).
            bpy.ops.export_scene.gltf(filepath=path, export_format="GLB",
                                      use_selection=True, use_active_scene=True,
                                      export_apply=True)
        elif fmt == "fbx":
            bpy.ops.export_scene.fbx(filepath=path, use_selection=True,
                                     apply_scale_options="FBX_SCALE_ALL")
        else:
            raise ValueError(f"unknown format {fmt!r}: glb or fbx")
    finally:
        root.matrix_world = saved_root
        for o in hidden:
            o.hide_set(True)
        lc.exclude, lc.hide_viewport = saved_lc
        bpy.ops.object.select_all(action="DESELECT")
        for o in saved_sel:
            if o.name in bpy.context.view_layer.objects:
                o.select_set(True)
    return path


def export_all(directory: str, fmt: str = "glb") -> list[str]:
    """export() every part."""
    return [export(n, directory, fmt) for n in parts()]
