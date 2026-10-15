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

# Fail the build rather than ship an image whose MCP add-on is missing or renamed.
addon = prefs.addons.get("bl_ext.user_default.mcp")
assert addon is not None, "MCP add-on is not enabled"
assert addon.preferences.use_autostart, "MCP add-on auto-start is off"
assert addon.preferences.host == "localhost", addon.preferences.host

bpy.ops.wm.save_userpref()
print("build-prefs: saved")
