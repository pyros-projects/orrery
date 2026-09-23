"""ComfyUI node pack for orrery.

Link this folder into ComfyUI:
    ln -s /path/to/orrery/comfyui /path/to/ComfyUI/custom_nodes/orrery
It puts the repo's src/ on the path, so ComfyUI's Python only needs PyYAML.
"""

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from orrery.comfy import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS
from orrery.completion import completion_data
from orrery.home import resolve_home

WEB_DIRECTORY = "./web"

try:
    from aiohttp import web
    from server import PromptServer
except ImportError:  # imported outside ComfyUI
    PromptServer = None

if PromptServer is not None:
    @PromptServer.instance.routes.get("/orrery/completions")
    async def _completions(request):
        return web.json_response(completion_data(resolve_home(request.query.get("home") or None)))

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
