"""ComfyUI node pack for orrery.

Clone the repository into ComfyUI's custom_nodes (its __init__.py loads this one), or link this
folder there:
    ln -s /path/to/orrery/comfyui /path/to/ComfyUI/custom_nodes/orrery
It puts the repo's src/ on the path, so ComfyUI's Python only needs PyYAML.
"""

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from orrery import __version__, banner, refbias
from orrery.comfy import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS
from orrery.comfy_refmods import pack_installed
from orrery.home import home_source
from orrery.webapi import register

strengths = refbias.install()  # a strength per RefMod: wraps H3's attention in memory, ComfyUI's files stay as they are

WEB_DIRECTORY = "./web"

try:
    from aiohttp import web
    from server import PromptServer
except ImportError:  # imported outside ComfyUI
    PromptServer = None

if PromptServer is not None:
    register(PromptServer.instance.routes, web)
    banner.note("nodes", " · ".join(name.removeprefix("Orrery ") for name in NODE_DISPLAY_NAME_MAPPINGS.values()))
    home, source = home_source()
    where = {"env": "ORRERY_HOME", "setting": "the setting"}.get(source, source)
    banner.note("home", f"{home} ({where})")
    if not pack_installed():
        banner.note("refmods", "ComfyUI-H3RefMods is not installed, so Orrery RefMods cannot load RefMods", "warn")
    elif strengths != "on":
        banner.note("refmods", f"strengths are off ({strengths}): every RefMod runs at 1", "warn")
    else:
        banner.note("refmods", "strengths on: orrery wraps H3's attention in memory, ComfyUI's files stay as they are")
    banner.show(__version__)

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
