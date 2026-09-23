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

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
