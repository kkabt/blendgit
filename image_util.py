import bpy

from .common import get_subpath


preview_collections = {}

GIT_ICONS = {
    'LOGO': "Git-Icon-1788C.png",
}

def get_icon(name: str) -> 'icon_id: int':
    pcoll = preview_collections["blendgit"]
    image = pcoll.get(name)
    return image.icon_id if image else 0


def register():

    pcoll = bpy.utils.previews.new()
    preview_collections["blendgit"] = pcoll

    # load icons
    for name, filename in GIT_ICONS.items():
        abspath = get_subpath("icons", filename)
        pcoll.load(name, abspath, 'IMAGE')


def unregister():
    for pcoll in preview_collections.values():
        bpy.utils.previews.remove(pcoll)
    preview_collections.clear()