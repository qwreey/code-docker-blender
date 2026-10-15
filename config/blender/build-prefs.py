# Run once at image build (`blender -b --python`), after the MCP add-on is installed:
# fixes the preferences the container needs and saves them as the image's userpref.blend.
import bpy

prefs = bpy.context.preferences

# The splash screen covers the middle of the window until someone clicks - and with no
# one watching, that is every screenshot the agent takes.
prefs.view.show_splash = False

# --online-mode (needed only for the MCP add-on's loopback socket) also lets Blender fetch
# the "Online Essentials" asset library and sync extensions.blender.org on startup. The
# container has no route out, so both just fail - the first one with an error in the
# status bar of every session. Turn them off instead of leaving the noise.
prefs.asset_libraries.use_online_essentials = False
for repo in prefs.extensions.repos:
    if repo.use_remote_url:
        repo.enabled = False

# Navigating the viewport over VNC. With continuous grab on (the default), a middle-drag
# rotate, a shift+middle pan or a drag on the navigation gizmo grabs the pointer so it can
# wrap around the screen, and from then on Blender reads relative motion only. A VNC
# viewer sends absolute positions and nothing else, so the view didn't move at all
# (measured: a middle-drag sent over RFB left view_rotation unchanged with it on, and
# rotated it with it off). The cost is that a drag stops at the window's edge.
prefs.inputs.use_mouse_continuous = False

# Where a render's result is shown. The MCP render tools render with INVOKE_DEFAULT,
# which by default opens a Render Result window - one that labwc's rule maximizes over
# Blender, hiding the person's scene, and that then sits in every later screenshot until
# someone closes it. With "keep user interface" the result opens nowhere; the files the
# tools write are unaffected (measured), and a person sees the last render with F11.
prefs.view.render_display_type = "NONE"

# Fail the build rather than ship an image whose MCP add-on is missing or renamed.
addon = prefs.addons.get("bl_ext.user_default.mcp")
assert addon is not None, "MCP add-on is not enabled"
assert addon.preferences.use_autostart, "MCP add-on auto-start is off"
assert addon.preferences.host == "localhost", addon.preferences.host

bpy.ops.wm.save_userpref()
print("build-prefs: saved")
