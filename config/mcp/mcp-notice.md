DEPLOYMENT (code-docker-blender) - overrides the general guidance below.
Blender runs in its own container as a live GUI that a person may be watching over VNC.
- Shared directory: {WORK_DIR}, the same path on both sides. Save .blend files, exports and renders there. Other paths exist on one side only.
- render_*_to_path keep only the file name and write under {WORK_DIR}/.tmp/. Use the path they return.
- The data/api and data/manual docs are not on your filesystem. Use search_api_docs, search_manual_docs and get_python_api_docs.
- To judge a model, render it from a camera (BLENDER_EEVEE or BLENDER_WORKBENCH, GPU, about 1 s) to a PNG in {WORK_DIR} and open it. Check several angles. get_screenshot_of_window_as_image shows what the person sees.
- execute_blender_code imports nothing for you. Start with `import bpy`.
- Models with parts: `import partkit` (one collection per part, each exported at its own origin). Workflow and file layout: /run/code-docker-blender/blender-modeler.md. When the person asks to see models, show them in the live window (`partkit.show()`), not only as PNGs.
- An unsaved scene is lost when Blender restarts. Save milestones to {WORK_DIR}.
- "Cannot connect to Blender" means it is starting or restarting. Wait a few seconds and retry.
- Leave the person's scene alone unless asked. Do new work in a new scene or file.
- No internet: extension installs, online assets and downloads fail.
