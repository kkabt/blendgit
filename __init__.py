''' ##### GNU GPL Version3 #####

BlendGit: Keep track of revisions of blend files in git from blender
Original work Copyright (C) 2012  scorpion81
Modified work Copyright (C) 2020  Kei Kabuto

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.

'''



bl_info = {
    "name": "BlendGit",
    "author": "scorpion81, Kei Kabuto",
    "support": "TESTING",
    "version": (3, 3, 5),
    "blender": (2, 83, 0),
    "location": "Sidebar -> Git",
    "description": "Keep track of revisions of blend files in git from blender",
    "warning": "",
    "wiki_url": "",
    "tracker_url": "",
    "category": "User",
    }



if "bpy" in locals():
    from importlib import reload as _r
    _r(props)
    _r(ops_main)
    _r(ops_extra)
    _r(ui)
    _r(image_util)
    _r(backend_git)
    _r(common)
else:
    from . import (
        props,
        ops_main,
        ops_extra,
        ui,
        image_util,
        backend_git,
        common
        )


import bpy
from bpy.props import *
from bpy.app import handlers

import sys


URL_DOCS = "https://git-scm.com/docs"
URL_LOGOS = "https://git-scm.com/downloads/logos"
URL_GITHUB = "https://github.com/"


class CommandShortcut(bpy.types.PropertyGroup):
    name: StringProperty()
    command: StringProperty()
    show_popup: BoolProperty()
    need_confirm: BoolProperty()


class GIT_OT_shortcut_add(bpy.types.Operator):
    bl_idname="git.shortcut_add"
    bl_label="Add Command Shortcut"
    bl_description=""
    bl_options={'INTERNAL', 'REGISTER', 'UNDO'}

    propname: StringProperty()

    def execute(self, context):
        prefs = common.get_addon_prefs(context)

        if hasattr(prefs, self.propname):
            coll = getattr(prefs, self.propname)
            coll.add()
        return {'FINISHED'}


class GIT_OT_shortcut_remove(bpy.types.Operator):
    bl_idname="git.shortcut_remove"
    bl_label="Remove Command Shortcut"
    bl_description=""
    bl_options={'INTERNAL', 'REGISTER', 'UNDO'}

    propname: StringProperty()
    index: IntProperty(default=-1)

    def execute(self, context):
        if self.index==-1:
            return {'CANCELLED'}

        prefs = common.get_addon_prefs(context)

        if hasattr(prefs, self.propname):
            coll = getattr(prefs, self.propname)
            coll.remove(self.index)
        return {'FINISHED'}




class BlendGitPreferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    active_tab: EnumProperty(
        items=[
            ('path', "Path", ""),
            ('log', "Log", ""),
            ('shortcut', "Shortcuts", ""),
            ('ui', "UI", ""),
            ('link', "Link", "")
            ],
        default='path'
        )

    def update_execpath(self, context):
        git = backend_git.Git(context)
        gcon = common.get_git_context(context)
        if git.operative:
            gcon.version = list(git.command(["version"]))[0]
        else:
            gcon.version = ""

    git_execpath: StringProperty(
        subtype='FILE_PATH',
        update=update_execpath
        )

    log_commands: CollectionProperty(type=CommandShortcut)
    log_command: EnumProperty(
        items=lambda s,c: [(cmd.command, cmd.name, "") for  cmd in s.log_commands],
        update=lambda s,c: ops_main.reload_logs(c)
        )

    # UI
    popup_width: IntProperty(
        name="Popup Width",
        min=100, max=1000,
        default=300
        )
    thumbnail_extension: EnumProperty(
        items=[
            ('none', "None", ""),
            ('fill', "Fill", ""),
            ],
        default='none'
        )
    show_panel_topbar: BoolProperty(default=True, name="Topbar Panel Popup Button")
    show_command_topbar: BoolProperty(default=True, name="Topbar Command Popup Button")
    show_v3d_panels: BoolProperty(default=True, name="3D View Panels")

    # shortcuts
    shortcuts: CollectionProperty(type=CommandShortcut)

    # archive
    archive_dir: StringProperty(
        name="Archive Directory",
        subtype='DIR_PATH',
        description="select:     [selected]/<project>/<commit_hash>.zip\nnot select: <project>/archive/<commit_hash>.zip"
        )

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.prop(self, 'active_tab', expand=True)
        layout.separator()

        tab = self.active_tab
        if tab == 'path':
            layout.prop(self, "git_execpath", text="git.exe")
            layout.prop(self, "archive_dir")

        elif tab == 'log':
            layout.label(text="Log Commands")
            if len(self.log_commands) > 0:
                split = layout.split(factor=0.3, align=True)
                col_name = split.column()
                col_cmd = split.column()

                col_name.label(text="Name", translate=False)
                col_cmd.label(text="Command", translate=False)
                for idx, sc in enumerate(self.log_commands):
                    col_name.prop(sc, "name", text="")
                    row = col_cmd.row(align=True)
                    row.prop(sc, "command", text="")
                    row.separator()
                    op = row.operator("git.shortcut_remove", text="", icon="REMOVE")
                    op.propname = 'log_commands'
                    op.index = idx
                layout.separator()
            layout.operator("git.shortcut_add", text="Add Log Command", icon="ADD").propname = 'log_commands'

        elif tab == 'shortcut':
            layout.label(text="Command Shortcuts")
            if len(self.shortcuts) > 0:
                split = layout.split(factor=0.3, align=True)
                col_name = split.column()
                col_cmd = split.column()

                col_name.label(text="Name", translate=False)
                col_cmd.label(text="Command", translate=False)
                for idx, sc in enumerate(self.shortcuts):
                    col_name.prop(sc, "name", text="")
                    row = col_cmd.row(align=True)
                    row.prop(sc, "command", text="")
                    row.prop(sc, "show_popup", text="", icon='WINDOW', toggle=True)
                    row.prop(sc, "need_confirm", text="", icon='ERROR', toggle=True)
                    row.separator()
                    op = row.operator("git.shortcut_remove", text="", icon="REMOVE")
                    op.propname = 'shortcuts'
                    op.index = idx
                layout.separator()
            layout.operator("git.shortcut_add", text="Add Command Shortcut", icon="ADD").propname = 'shortcuts'

        elif tab == 'ui':
            layout.use_property_split = True
            layout.label(text="Panel", icon='MENU_PANEL')
            layout.prop(self, 'show_panel_topbar')
            layout.prop(self, 'show_command_topbar')
            layout.prop(self, 'show_v3d_panels')

            layout.separator()

            layout.label(text="Popup", icon='WINDOW')
            layout.prop(self, 'popup_width', slider=True)
            layout.prop(self, 'thumbnail_extension', text="Thumbnail Extention", expand=True)

        elif tab == 'link':
            grid = layout.grid_flow(even_columns=True)
            grid.operator("wm.url_open", text="Git Documentation", icon='URL').url = URL_DOCS
            grid.operator("wm.url_open", text="GitHub", icon='URL').url = URL_GITHUB

            layout.separator()

            layout.label(text="Credit")
            credit = "Icon by Jason Long - Orange logomark for light backgrounds"
            val = image_util.get_icon('LOGO')
            row = layout.row(align=True)
            row.label(text=credit, icon_value=val)
            row.operator("wm.url_open", text="", icon='URL').url = URL_LOGOS



classes = (
    CommandShortcut,
    GIT_OT_shortcut_add,
    GIT_OT_shortcut_remove,
    BlendGitPreferences,
    *props.classes,
    *ops_main.classes,
    *ops_extra.classes,
    *ui.classes,
    )


@handlers.persistent
def file_handler(dummy):
    bpy.context.window_manager.git_context.rootdir = bpy.path.abspath("//")
    bpy.ops.git.reload('INVOKE_DEFAULT')


@handlers.persistent
def data_handler(dummy):
    for lib in (bpy.data.textures, bpy.data.images):
        for data in lib:
            dot, *hs = data.name
            if dot=="." and common.extract_hash(hs):
                data.user_clear()


_draw_right = None

def draw_right(self, context):
    layout = self.layout
    prefs = common.get_addon_prefs(context)

    row = layout.row(align=True)
    if prefs.show_panel_topbar:
        row.operator("git.panel_popup", text="", icon_value=image_util.get_icon('LOGO'))
    if prefs.show_command_topbar:
        row.operator("git.command_popup", text="", icon='CONSOLE')
    layout.separator()
    _draw_right(self, context)


def register():
    image_util.register()

    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)

    props.register()

    handlers.save_pre.append(data_handler)

    handlers.load_post.append(file_handler)
    handlers.save_post.append(file_handler)

    global _draw_right
    _draw_right = bpy.types.TOPBAR_HT_upper_bar.draw_right
    bpy.types.TOPBAR_HT_upper_bar.draw_right = draw_right

    
def unregister():
    bpy.types.TOPBAR_HT_upper_bar.draw_right = _draw_right

    handlers.save_post.remove(file_handler)
    handlers.load_post.remove(file_handler)

    handlers.save_pre.remove(data_handler)

    props.unregister()

    from bpy.utils import unregister_class
    for cls in reversed(classes):
        unregister_class(cls)

    image_util.unregister()


if __name__ == "__main__":
    register()