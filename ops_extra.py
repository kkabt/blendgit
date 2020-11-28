import bpy
from bpy.types import Operator
from bpy.props import *
import bgl
import gpu
from gpu_extras.batch import batch_for_shader

import shutil
import os
import zipfile

from .backend_git import Git
from . import common
from .common import (
    get_git_context as g,
    get_addon_prefs as p
    )
from .image_util import get_icon

from .ops_main import (
    reload_files,
    get_thumbnail_path,
    update_thumbnail,
    GitOperator,
    FileOperator,
    LogOperator
    )
from .ui import panels


# @classmethod
    # def result_to_text(cls, self, context):
    #     if self.add_text:
    #         text = bpy.data.texts.new("git_command_result")
    #         text.write(f">$git {cls.__last_command}\n")
    #         for line in cls.__last_lines:
    #             text.write(line+"\n")
    #         self.add_text = False
    #         self.report({'INFO'}, f"Write result to {text.name}")


# +++++++++++++++++++++++++++++++++++++++++++++
#
#   Class
#
# +++++++++++++++++++++++++++++++++++++++++++++

# GIT_OT_open_folder
# GIT_OT_panel_popup
# GIT_OT_command_popup
# GIT_OT_write_ignore
# GIT_OT_show
# GIT_OT_thumbnail_edit
# GIT_OT_thumbnail_snipping
# GIT_OT_checkout_file
# GIT_OT_pick_library
# GIT_OT_archive


class GIT_OT_open_folder(GitOperator):
    bl_idname = "git.open_folder"
    bl_label = "Open Folder"
    bl_description = "Open explorer with selected path"

    dirpath: StringProperty()

    def execute(self, context):

        if self.dirpath:
            dirpath = self.dirpath
        else:
            dirpath = bpy.path.abspath("//")

        exists = self.git.open_dir(dirpath)
        if not exists:
            self.report({'ERROR'}, "Not exists: "+self.dirpath)
        return {'FINISHED'}


class GIT_OT_panel_popup(GitOperator):
    bl_idname = "git.panel_popup"
    bl_label = "Popup Git Panel"
    bl_description = "Popup Git Panel"

    panel_selector: EnumProperty(
        items=[('all', "All", "")] + [
            (
                p.__name__,
                p.__name__.replace("GIT_PT_", ""),
                ""
            )
            for p in panels
            ],
        default='all'
        )
    panel_dict = {p.__name__: p for p in panels}

    @classmethod
    def poll(cls, context):
        super().poll(context)
        return True

    def invoke(self, context, event):
        prefs = p(context)
        wm = context.window_manager
        return wm.invoke_popup(self, width=prefs.popup_width)

    def draw(self, context):
        def draw_panel(layout, panel):
            if panel.poll(context):
                name = panel.__name__[7:]
                header = name[0].upper() + name[1:]
                layout.label(text=header, translate=False)
                panel._draw(layout, context)
                layout.separator()

        layout = self.layout

        gcon = g(context)
        row = layout.row()
        row.label(text=gcon.version, icon_value=get_icon('LOGO'))
        # sub = row.row()
        row.prop(self, 'panel_selector', text="", translate=False)
        # sub.ui_units_x = 4
        layout.separator()

        if self.panel_selector != 'all':
            panel = self.panel_dict[self.panel_selector]
            draw_panel(layout, panel)
        else:
            for panel in panels:
                draw_panel(layout, panel)

    def execute(self, context):
        return {'INTERFACE'}


class GIT_OT_command_popup(GitOperator):
    bl_idname = "git.command_popup"
    bl_label = "Git Command Popup"
    bl_description = "Open command action popup"
    bl_options = GitOperator.popup_options

    @staticmethod
    def replace_keyword(context, command):
        gcon = g(context)
        branchname = gcon.branches[gcon.active_branch].name if len(gcon.branches) else ""
        file_ref = gcon.files[gcon.active_file].ref if len(gcon.files) else ""
        stash_rev = gcon.stashes[gcon.active_stash].revision if len(gcon.stashes) else ""
        commit_hash = gcon.logs[gcon.active_log].commit_hash if len(gcon.logs) else ""
        d = {
            '<branch>': branchname,
            '<file>': file_ref,
            '<stash>': stash_rev,
            '<commit>': commit_hash
            }
        cmd = command
        for k,v in d.items():
            if k in cmd:
                cmd = cmd.replace(k, v)
        return cmd

    @classmethod
    def run_command(cls, context, command):
        if command:
            cmd = cls.replace_keyword(context, command)
            cls.command(cmd)
            cls.last_command = cmd
            cls.last_lines.clear()

    last_lines = []
    last_command = ""

    dialog_command: StringProperty(
        update=lambda s,c: __class__.run_command(c, s.dialog_command),
        options={'SKIP_SAVE'},
        )
    pre_command: StringProperty()

    show_popup: BoolProperty()
    need_confirm: BoolProperty()
    # need_input: BoolProperty()

    def invoke(self, context, event):
        wm = context.window_manager
        prefs = p(context)

        if not self.pre_command:
            return wm.invoke_popup(self, width=prefs.popup_width)

        if self.need_confirm:
            return wm.invoke_props_dialog(self)
        
        self.run_command(context, self.pre_command)

        if self.show_popup:
            return wm.invoke_popup(self, width=prefs.popup_width)
        else:
            return {'FINISHED'}

    def execute(self, context):
        if self.need_confirm:
            self.run_command(context, self.pre_command)
            self.need_confirm = False

            if self.show_popup:
                wm = context.window_manager
                prefs = p(context)
                return wm.invoke_popup(self, width=prefs.popup_width)
        return {'FINISHED'}

    def draw(self, context):
        layout = self.layout

        if self.need_confirm:
            layout.label(text=f"{self.pre_command}")

        else:
            if not self.pre_command:
                row = layout.row(align=True)
                sub1 = row.row(align=True)
                sub1.label(text="$ git ")
                sub1.ui_units_x = 1

                sub2 = row.row(align=True)
                sub2.activate_init=True
                sub2.prop(self, "dialog_command", text="")

                layout.separator()

            if self.last_command:
                box = layout.box()
                box.label(text=f">$git {self.last_command}")
                box.separator()
                col = box.column(align=True)
                cnt = 0
                try:
                    results = self.get_results()
                    while True:
                        line = next(results)
                        common.spaced_label(col, line)

                        if len(self.last_lines) != cnt:
                            self.last_lines.clear()

                        self.last_lines.append(line)
                        cnt += 1
                except StopIteration:
                    if not cnt:
                        for line in self.last_lines:
                            common.spaced_label(col, line)

                # layout.operator(git.result_to_text)


class GIT_OT_write_ignore(FileOperator):
    bl_idname = "git.write_ignore"
    bl_label = "Write Ignore"
    bl_description = "Write line to .gitignore"

    line: StringProperty(name="Line")

    def __init__(self):
        lines = []

    def invoke(self, context, event):
        if not os.path.isfile(Git.PATH_GITIGNORE):
            with open(Git.PATH_GITIGNORE, "w+") as f:
                pass

        with open(Git.PATH_GITIGNORE, "r") as f:
            self.lines = f.read().split('\n')
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'line')
        layout.separator()
        layout.label(text=Git.PATH_GITIGNORE, icon='FILE')
        box = layout.box()
        for line in self.lines:
            box.label(text=line)

    def execute(self, context):
        self.git.write_ignore(self.line)
        reload_files(context)
        return {'FINISHED'}


# restore_stack[cls]: bool(restoring)
restore_stack = {}

class StandardColor:
    '''
    For displaying thumbnail with standard color,
    need to prevent ImageTexture to be view-trarnsformed.
    '''

    def __init__(self):
        self.old_vt = ""

    def cancel(self, context):
        self.restore(context)

    def normalize(self, context):
        # for display imagetexture standard color
        sc = context.scene
        self.old_vt = sc.view_settings.view_transform
        sc.view_settings.view_transform = 'Standard'
        restore_stack[self.__class__] = False

    def restore(self, context):
        restore_stack[self.__class__] = True
        if all(restore_stack.values()):
            context.scene.view_settings.view_transform = self.old_vt
            restore_stack.clear()

    def draw_thumbnail(self, context, layout, log, popup_width=0):
        thumbnail = log.thumbnail
        if thumbnail and thumbnail.image:
            prefs = p(context)

            (x, y) = thumbnail.image.size
            w = popup_width or prefs.popup_width
            h = 16*9
            # template_preview default ui_units_y?

            col = layout.column()

            ext = prefs.thumbnail_extension
            if y > w:
                ext = 'fill'
            if ext == 'none':
                col.scale_x = min(1, x / w)
                col.scale_y = y / h
            elif ext == 'fill':
                col.scale_y = w*y / (h*x)

            col.template_preview(thumbnail, show_buttons=False)


class GIT_OT_show(LogOperator, StandardColor):
    bl_idname = "git.show"
    bl_label = "Show Commit"
    bl_description = "$git show <commit>"
    bl_options = GitOperator.popup_options

    def invoke(self, context, event):
        self.normalize(context)

        wm = context.window_manager
        prefs = p(context)
        return wm.invoke_popup(self, width=prefs.popup_width)

    def draw(self, context):
        log = self.get_entry()
        c_hash = log.commit_hash

        self.command(["show", c_hash])

        col = self.layout.column(align=True)
        col.label(text = f'$git show {c_hash}')
        col.separator()
        for line in self.get_results():
            common.spaced_label(col, line)

        # draw Thumbnail
        self.draw_thumbnail(context, col, log)

    def execute(self, context):
        return {'INTERFACE'}


class GIT_OT_thumbnail_edit(LogOperator, StandardColor):
    bl_idname = "git.thumbnail_edit"
    bl_label = "Edit Thumbnail"
    bl_description = "Edit thumbnail of active log"

    source: EnumProperty(
        items=[
            ('none', "None", "Unset Thumbnail"),
            ('snip', "Snipping", "Snipping Screen"),
            ('file', "File", "File Select"),
            ],
        default='snip'
        )
    filepath: StringProperty(subtype='FILE_PATH')


    def invoke(self, context, event):
        self.normalize(context)

        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout

        self.draw_thumbnail(context, layout, self.get_entry(), popup_width=300)

        layout.prop(self, 'source', text="Source", expand=True, translate=False)
        if self.source == 'none':
            layout.alert = True
            layout.label(text="Delete thumbnail", icon='ERROR')

    def execute(self, context):
        log = self.get_entry()
        thumbnail_path = get_thumbnail_path(
            context,
            log.commit_hash
            )

        dirpath = ".git/.git_thumbnails"
        if not os.path.isdir(dirpath):
            os.makedirs(dirpath, exist_ok=True)

        if self.source == 'none':
            img = log.thumbnail.image
            if img:
                os.remove(img.filepath)
                bpy.data.images.remove(img)
                self.report({'INFO'}, f"Remove thumbnail from {log.commit_hash}")
        elif self.source == 'snip':
            bpy.ops.git.thumbnail_snipping('INVOKE_DEFAULT', filepath=thumbnail_path)
        elif self.source == 'file':
            if not self.filepath:
                context.window_manager.fileselect_add(self)
                return {'RUNNING_MODAL'}
            else:
                if os.path.isfile(self.filepath):
                    shutil.copy(self.filepath, thumbnail_path)

                    update_thumbnail(context, log)
                    self.report({'INFO'}, f"Set thumbnail for {log.commit_hash}")

        self.restore(context)
        return {'FINISHED'}



class GIT_OT_thumbnail_snipping(LogOperator, StandardColor):
    bl_idname = "git.thumbnail_snipping"
    bl_label = "Snipping for thumbnail"
    bl_description = "Take a snipped screenshot for thumbnail"

    filepath: StringProperty(subtype='FILE_PATH')

    def __init__(self):
        super().__init__()

        # {area: {region: handle, ...}, ...}
        self.__handles = {}

        (self.__x0, self.__y0) = (0, 0)
        (self.__x1, self.__y1) = (0, 0)

        self.pressed = False

    def is_running(self):
        return bool(self.__handles)

    def plot(self, index, x, y):
        if index == 0:
            (self.__x0, self.__y0) = (x, y)
        elif index == 1:
            (self.__x1, self.__y1) = (x, y)

    def get_rect(self):
        return (self.__x0, self.__y0), (self.__x1, self.__y1)

    def handle_add(self, context):
        if not self.is_running():
            for area in context.screen.areas:
                handles = {}
                for region in area.regions:
                    hndl = area.spaces[0].draw_handler_add(self.__draw, (context, region), region.type, 'POST_PIXEL')
                    handles[region] = hndl
                self.__handles[area] = handles
                area.tag_redraw()

    def handle_remove(self, context):
        if self.is_running():
            for area, handles in self.__handles.items():
                for region, hndl in handles.items():
                    area.spaces[0].draw_handler_remove(hndl, region.type)
                    area.tag_redraw()
            self.__handles.clear()

    def __draw(self, context, region):
        
        shader = gpu.shader.from_builtin('2D_UNIFORM_COLOR')
        indices = [[0, 1, 2], [2, 3, 0]]
        def batch_draw(data, color):
            bgl.glEnable(bgl.GL_BLEND)
            batch = batch_for_shader(shader, 'TRIS', data, indices=indices)
            shader.bind()
            shader.uniform_float("color", color)
            batch.draw(shader)
            bgl.glDisable(bgl.GL_BLEND)

        data = {}

        # draw disactive area
        data["pos"] = [
            [0, 0],
            [region.width, 0],
            [region.width, region.height],
            [0, region.height]
            ]
        color = [0.0, 0.0, 0.0, 0.5]  # black
        batch_draw(data, color)

        # draw snipping region
        (x0, y0), (x1, y1) = self.get_rect()
        (rx0, ry0) = (x0 - region.x, y0 - region.y)
        (rx1, ry1) = (x1 - region.x, y1 - region.y)
        data["pos"] = [
            [rx0, ry0],
            [rx0, ry1],
            [rx1, ry1],
            [rx1, ry0]
            ]
        color = [1.0, 0.0, 0.0, 0.1]  # red
        batch_draw(data, color)


    def invoke(self, context, event):
        self.normalize(context)

        if not self.filepath:
            self.filepath = get_thumbnail_path(
                context,
                self.get_entry().commit_hash
                )

        self.handle_add(context)

        context.window_manager.modal_handler_add(self)

        print('Start Modal')

        return {'RUNNING_MODAL'}


    def modal(self, context, event):

        # mouse events
        if event.type == 'LEFTMOUSE':

            if event.value == 'PRESS':
                self.plot(0, event.mouse_x, event.mouse_y)
                self.plot(1, event.mouse_x, event.mouse_y)
                self.pressed = True
                print('PRESS', self.get_rect()[0])

            elif event.value == 'RELEASE':
                print('RELEASE', self.get_rect()[1])
                self.handle_remove(context)
                return self.execute(context)

        elif self.pressed and event.type == 'MOUSEMOVE':
            self.plot(1, event.mouse_x, event.mouse_y)

        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            print('CANCELLED')
            self.handle_remove(context)
            return {'CANCELLED'}

        # redraw screen
        for area in self.__handles.keys():
            area.tag_redraw()

        return {'RUNNING_MODAL'}


    def execute(self, context):

        # 1. take SS /w "temppath"
        # 2. background composition /w "filepath"

        # take SS
        tempdir = context.preferences.filepaths.temporary_directory
        temppath = tempdir+"image0001.png"
        bpy.ops.screen.screenshot(filepath=temppath, check_existing=False)


        # compose SS and output file
        sc = context.scene
        old_setting = sc.use_nodes
        sc.use_nodes = True

        node_tree = sc.node_tree
        nodes = node_tree.nodes
        links = node_tree.links

        # image -> crop -> file
        img = nodes.new(type='CompositorNodeImage')
        img.image = bpy.data.images.load(temppath)

        crop = nodes.new(type='CompositorNodeCrop')
        crop.use_crop_size = True
        ((x0, y0), (x1, y1)) = self.get_rect()
        crop.min_x = min(x0, x1)
        crop.min_y = min(y0, y1)
        crop.max_x = max(x0, x1)
        crop.max_y = max(y0, y1)

        file = nodes.new(type='CompositorNodeOutputFile')
        file.base_path = tempdir

        links.new(img.outputs[0], crop.inputs[0])
        links.new(crop.outputs[0], file.inputs[0])

        bpy.ops.render.render()

        shutil.move(temppath, self.filepath)

        # clean up
        for n in (img, crop, file):
            nodes.remove(n)

        sc.use_nodes = old_setting

        # set thumbnail
        update_thumbnail(context, self.get_entry())
        self.restore(context)


        self.report({'INFO'}, f"Snipping screen to {self.filepath}")
        return {'FINISHED'}


class GIT_OT_checkout_file(LogOperator):
    bl_idname = "git.checkout_file"
    bl_label = "Checkout file"
    bl_description = "Checkout file from other branch"

    def update_file(self, context):
        ref = bpy.path.abspath(g(context).rootdir)
        self.discarding = self.file == ref

    file: EnumProperty(
        items=lambda s,c: [(f, f, "") for f in __class__.get_results(str).split('\n')],
        update=update_file
        )
    discarding: BoolProperty(options={'HIDDEN'})

    def __init__(self):
        discarding = False

    def invoke(self, context, event):
        log = self.get_entry()
        self.command(["ls-tree", "-r", "--name-only", log.commit_hash])

        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.label(text=self.get_entry().commit_hash)
        layout.prop(self, 'file')
        
        if self.discarding:
            common.alert(layout, "Checkout is to discard recent edits")

    def execute(self, context):
        log = self.get_entry()
        self.command(
            ["checkout", log.commit_hash, "--", self.file],
            reporter=self
            )
        if self.discarding:
            bpy.ops.wm.revert_mainfile()
        else:
            reload_files(context)
        return {'FINISHED'}


# for git.pick_library / git.archive
class GIT_PR_pickable(bpy.types.PropertyGroup):
    pick: BoolProperty()
    show_expand: BoolProperty()
    type: StringProperty()


class GIT_OT_pick_library(LogOperator):
    bl_idname = "git.pick_library"
    bl_label = "Pick Library"
    bl_description = "Pick library data from old file"

    def file_items(self, context):
        items = []
        log = __class__.get_entry()
        for name, blobnr in Git(context).get_blobs(log.commit_hash).items():
            if name.endswith(".blend"):
                items.append((blobnr, name, ""))
        return items

    def file_update(self, context):
        tmppath = common.get_subpath("tmp.blend")
        Git(context).backup(
            self.file,
            tmppath
            )
        # load data
        self.libraries.clear()
        with bpy.data.libraries.load(tmppath) as (data_from, data_to):
            cls = __class__
            for attr in dir(data_to):
                cls.name_max = max(cls.name_max, len(attr))
                data = getattr(data_from, attr)
                if data:
                    lib = self.libraries.add()
                    lib.name = attr
                    for name in data:
                        lib = self.libraries.add()
                        lib.name = name
                        lib.type = attr

    name_max = 0
    file: EnumProperty(
        items=file_items,
        update=file_update
        )
    # tag: show_expand, filepath: type, use_fake_user: pick
    libraries: CollectionProperty(type=GIT_PR_pickable, options={'HIDDEN'})

    link_objects: BoolProperty(description="Link objects to scene")
    link_collections: BoolProperty(description="Link collections to scene")

    def invoke(self, context, event):
        if self.file:
            self.file_update(context)

        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout

        layout.prop(self, 'file')
        layout.separator()

        types = [l for l in self.libraries if not l.type]
        for typ in types:
            row = layout.row()
            libs = [l for l in self.libraries if l.type==typ.name]

            icon_expand = 'DISCLOSURE_TRI_DOWN' if typ.show_expand else 'DISCLOSURE_TRI_RIGHT'
            row.prop(typ, 'show_expand', text="", icon=icon_expand, emboss=False)

            spacing = " "*(self.name_max-len(typ.name))
            count = f" *{len([l for l in libs if l.pick])}/{len(libs)}"
            row.label(text=f"{typ.name}{spacing}{count}")
            

            if typ.show_expand:
                row = layout.row()
                row.label(text="", icon='BLANK1')
                col = row.column()
                for lib in libs:
                    row = col.row(align=True)
                    row.prop(lib, 'pick', text="", icon='IMPORT', toggle=True)
                    row.label(text=lib.name, translate=False)

        layout.separator()
        layout.prop(self, 'link_objects', text="Link Object")
        layout.prop(self, 'link_collections', text="Link Collection")

    def execute(self, context):
        tmppath = common.get_subpath("tmp.blend")
        with bpy.data.libraries.load(tmppath) as (data_from, data_to):
            types = [l for l in self.libraries if not l.type]
            for typ in types:
                pickable = [l.name for l in self.libraries if l.type==typ.name and l.pick]
                setattr(data_to, typ.name, pickable)

        master = context.scene.collection
        log = self.get_entry()
        coll = bpy.data.collections.new(log.commit_hash)

        # link objects
        if self.link_objects and data_to.objects:
            coll_obj = bpy.data.collections.new("objects")
            for o in data_to.objects:
                coll_obj.objects.link(o)
            coll.children.link(coll_obj)

        # link collections
        if self.link_collections and data_to.collections:
            for c in data_to.collections:
                coll.children.link(c)

        if not coll.objects and not coll.children:
            bpy.data.collections.remove(coll)
        else:
            master.children.link(coll)

        self.report({'INFO'}, f"Pick library data from {self.get_entry().commit_hash}")
        return {'FINISHED'}


class GIT_OT_archive(LogOperator):
    bl_idname = "git.archive"
    bl_label = "Archive"
    bl_description = "$git archive"

    include_log: BoolProperty(
        name="Include Log",
        description="Show-command results to be written in log.text"
        )

    files: CollectionProperty(type=GIT_PR_pickable, options={'HIDDEN'})
    others: CollectionProperty(type=GIT_PR_pickable, options={'HIDDEN'})

    def invoke(self, context, event):
        log = self.get_entry()
        self.command(["ls-tree", "-r", "--name-only", log.commit_hash])
        self.files.clear()
        for line in self.get_results():
            f = self.files.add()
            f.name = line

        self.command(["ls-files", "-o"])
        self.others.clear()
        for line in self.get_results():
            f = self.others.add()
            f.name = line

        wm = context.window_manager
        # return wm.invoke_confirm(self, event)
        return wm.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        # file list
        layout.label(text="Tracked Files", icon='FILE')
        row = layout.row()
        row.label(text="", icon='BLANK1')
        col = row.column()
        for f in self.files:
            col.label(text=f.name)
        layout.separator()
        # include other files
        # layout.label(text="Other Files", icon='GHOST_DISABLED')
        layout.label(text="Other Files", icon='GHOST_DISABLED')
        row = layout.row()
        row.label(text="", icon='BLANK1')
        col = row.column()
        for f in self.others:
            col.prop(f, 'pick', text=f.name)
        layout.separator()
        # include log
        layout.prop(self, 'include_log', text="Include Log")

    def execute(self, context):
        c_hash = self.get_entry().commit_hash

        if c_hash == "":
            return {'CANCELLED'}

        dirpath = common.get_archive_path(context)

        if not os.path.isdir(dirpath):
            os.makedirs(dirpath, exist_ok=True)
            if os.path.basename(dirpath) == "archive":
                self.git.write_ignore(dirpath)

        filename = f"{dirpath}\\{c_hash}.zip"

        self.command(["archive", c_hash, "-o", filename])
        self.report({'INFO'}, "Archived: "+filename)

        # add log to zip file
        with zipfile.ZipFile(filename, "a") as z:
            if self.include_log:
                self.command(["show", c_hash])
                z.writestr(
                    "commit_log.txt",
                    self.get_results(str)
                    )
            for o in self.others:
                if o.pick:
                    z.write(o.name)

        reload_files(self, context)
        return {'FINISHED'}



classes = (
    GIT_OT_open_folder,
    GIT_OT_panel_popup,
    GIT_OT_command_popup,
    GIT_OT_write_ignore,
    GIT_OT_show,
    GIT_OT_thumbnail_edit,
    GIT_OT_thumbnail_snipping,
    GIT_OT_checkout_file,
    GIT_PR_pickable,  # for git.pick_library / git.archive
    GIT_OT_pick_library,
    GIT_OT_archive
    )