"""ComfyUI entry when the repository itself sits in custom_nodes (git clone, ComfyUI Manager).

A link to the comfyui/ folder works too and skips this file; both load the same nodes and app.
"""

if __package__:  # ComfyUI loads this as a package; pytest also imports it on its own, as a plain module
    from .comfyui import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

    WEB_DIRECTORY = "./comfyui/web"
    __all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
