import bpy
from bpy.types import Menu, UIList, Panel

from .backend_git import Git
from .image_util import get_icon
from . import common
from .common import (
    alert,
    get_git_context as g,
    get_addon_prefs as p
    )


ICON_STATUS = {
    Git.STATUS_UNMODIFIED: 'FILE_HIDDEN',
    Git.STATUS_IGNORED: 'GHOST_DISABLED',
    Git.STATUS_UNTRACKED: 'UNLINKED',
    Git.STATUS_UNMERGED: 'LIBRARY_DATA_BROKEN',
    Git.STATUS_NOTSTAGED: 'UNPINNED',
    Git.STATUS_STAGED: 'PINNED'
    }

ICON_COMMAND = {
    'stage': 'PINNED',
    'unstage': 'UNPINNED',
    'untrack': 'UNLINKED',
    'ignore': 'GHOST_DISABLED',
    'notice': 'HIDE_OFF'
    }



class GitPanel(Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Git"

    @classmethod
    def poll(cls, context):
        show = p(context).show_v3d_panels
        gcon = g(context)
        return show and gcon.version and gcon.is_repository
    

class GIT_PT_context(GitPanel):
    bl_label = ""

    @classmethod
    def poll(cls, context):
        return p(context).show_v3d_panels

    def draw_header(self, context):
        layout = self.layout

        gcon = g(context)
        if gcon.version:
            layout.label(
                text=gcon.version,
                icon_value=get_icon('LOGO')
                )
        else:
            alert(layout, "git.exe is NOT found")

    def draw(self, context):
        self._draw(self.layout, context)

    @staticmethod
    def _draw(layout, context):
        gcon = g(context)

        grid = layout.grid_flow(even_columns=True)
        grid.operator("preferences.addon_show", text="Open Setting", icon='PREFERENCES').module = "blendgit"

        grid.operator("git.reload", text="Reload", icon='FILE_REFRESH', translate=False)

        row = grid.row()
        row.operator("git.open_folder", text="Open Root", icon='FILE_FOLDER', translate=False).dirpath = gcon.rootdir
        row.enabled = bool(gcon.rootdir)

        row = grid.row()
        row.operator("git.load", text="Unload Repository", translate=False, icon='TRASH').unload = True
        row.enabled = gcon.is_repository


class GIT_PT_init(GitPanel):
    bl_label = ""

    def draw_header(self, context):
        self.layout.label(text="Init", translate=False)

    @classmethod
    def poll(cls, context):
        show = p(context).show_v3d_panels
        gcon = g(context)
        return show and gcon.version and not gcon.is_repository

    def draw(self, context):
        self._draw(self.layout, context)

    @staticmethod
    def _draw(layout, context):
        grid = layout.grid_flow(even_columns=True)
        grid.operator("git.load", text="Load Repository", icon='NEWFOLDER')
        grid.operator("git.init", text="Initialize Repository", icon='NEWFOLDER')


class GIT_PT_shortcut(GitPanel):
    bl_label = "Shortcut"

    def draw_header(self, context):
        layout = self.layout
        layout.operator("git.command_popup", text="", icon='CONSOLE', emboss=False)

    def draw(self, context):
        self._draw(self.layout, context)
        
    @staticmethod
    def _draw(layout, context):
        prefs = p(context)
        if len(prefs.shortcuts) == 0:
            layout.label(text="No shortcuts.")
        else:
            grid = layout.grid_flow(even_columns=True)
            for sc in prefs.shortcuts:
                if sc.name and sc.command:
                    op = grid.operator("git.command_popup", text=sc.name, translate=False)
                    op.pre_command = sc.command
                    op.show_popup = sc.show_popup
                    op.need_confirm = sc.need_confirm


class GIT_MT_switch(Menu):
    bl_label = "Switch"

    def draw(self, context):
        layout = self.layout

        gcon = context.window_manager.git_context
        active = gcon.active_branch
        for i, branch in enumerate(gcon.branches):
            if i==active:
                continue
            layout.operator("git.switch", text=branch.name).branchname = branch.name


class GIT_MT_branch(Menu):
    bl_label = "Branch"

    def draw(self, context):
        gcon = context.window_manager.git_context
        layout = self.layout

        layout.operator("git.branch_add", text="Add", translate=False)
        layout.operator("git.branch_rename", text="Rename", translate=False)
        layout.operator("git.branch_copy", text="Copy", translate=False)
        layout.operator("git.branch_delete", text="Delete", translate=False)
        layout.separator()
        layout.operator("git.merge", text="Merge", translate=False)


class GIT_PT_branch(GitPanel):
    bl_label = "Branch"

    def draw_header(self, context):
        gcon = g(context)
        if len(gcon.branches)>0:
            branchname = gcon.branches[gcon.active_branch].name
            self.bl_label = "Branch * "+branchname

    def draw(self, context):
        self._draw(self.layout, context)
        
    @staticmethod
    def _draw(layout, context):        
        gcon = g(context)
        if len(gcon.branches)>0:
            if gcon.is_dirty:
                alert(layout, "Your local changes to the following files would be overwritten by checkout")
                if gcon.status & Git.STATUS_UNTRACKED:
                    alert(layout, "The following untracked working tree files would be overwritten by checkout")
            
            row = layout.row()

            col = row.column()
            branch = gcon.branches[gcon.active_branch]
            col.menu("GIT_MT_switch", text=branch.name)
            col.enabled = not gcon.is_dirty and len(gcon.branches) > 1

            row.menu("GIT_MT_branch", icon='DOWNARROW_HLT', text="")
        else:
            layout.label(text="No branches.")


class GIT_MT_file(Menu):
    bl_label = "File"

    def draw(self, context):
        layout = self.layout

        layout.operator("git.write_ignore", icon=ICON_STATUS[Git.STATUS_IGNORED])


class GIT_UL_file(UIList):
    """For FileEntry"""
    show_unmodified: bpy.props.BoolProperty(default=True)
    show_ignored: bpy.props.BoolProperty(default=True)

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        gcon = data
        file = item

        status = file.status
        row = layout.row()

        row.label(text=file.name, icon=ICON_STATUS[status])

        row_op = row.row(align=True)

        if status == Git.STATUS_IGNORED:
            row_op.operator("git.notice", text="", icon=ICON_COMMAND['notice']).target_ref = file.ref

        else:
            if status in (
                Git.STATUS_UNTRACKED,
                Git.STATUS_UNMERGED,
                Git.STATUS_NOTSTAGED
                ):
                row_op.operator("git.stage", text="", icon=ICON_COMMAND['stage']).target_ref = file.ref

            if status == Git.STATUS_UNTRACKED:
                row_op.operator("git.ignore", text="", icon=ICON_COMMAND['ignore']).target_ref = file.ref

            # elif status == Git.STATUS_UNMERGED:
            #     op = row_op.operator("git.unstage", text="", icon='FILE_TICK')
            #     op.target_ref = file.ref
            #     op.resolve_unmerge = True

            elif status in (
                Git.STATUS_UNMODIFIED,
                Git.STATUS_NOTSTAGED
                ):
                row_op.operator("git.untrack", text="", icon=ICON_COMMAND['untrack']).target_ref = file.ref

            elif status == Git.STATUS_STAGED:
                if len(gcon.logs) == 0:
                    row_op.operator("git.untrack", text="", icon=ICON_COMMAND['untrack']).target_ref = file.ref

                else:
                    row_op.operator("git.unstage", text="", icon=ICON_COMMAND['unstage']).target_ref = file.ref


    def draw_filter(self, context, layout):
        row = layout.row()

        subrow = row.row(align=True)
        subrow.prop(self, "filter_name", text="")
        subrow.prop(self, "use_filter_invert", text="", icon='ARROW_LEFTRIGHT')

        subrow = row.row(align=True)
        subrow.prop(self, "show_unmodified", text="", toggle=True, icon=ICON_STATUS[Git.STATUS_UNMODIFIED])
        subrow.prop(self, "show_ignored", text="", toggle=True, icon=ICON_STATUS[Git.STATUS_IGNORED])


    def filter_items(self, context, data, propname):
        files = getattr(data, propname)
        helper_funcs = bpy.types.UI_UL_list

        # Default return values.
        flt_flags = []
        flt_neworder = []

        # Filtering by name
        if self.filter_name:
            flt_flags = helper_funcs.filter_items_by_name(
                self.filter_name,
                self.bitflag_filter_item,
                files,
                'name',
                reverse=self.use_filter_invert
                )

        if not flt_flags:
            flt_flags = [self.bitflag_filter_item] * len(files)

        # Filtering by show-ignored.
        for idx, file in enumerate(files):
            status = file.status
            if not self.show_unmodified and status==Git.STATUS_UNMODIFIED:
                flt_flags[idx] &= False
            elif not self.show_ignored and status==Git.STATUS_IGNORED:
                flt_flags[idx] &= False

        return flt_flags, flt_neworder


class GIT_PT_file(GitPanel):
    bl_label = ""
    
    def draw_header(self, context):
        layout = self.layout
        layout.label(text="File", translate=False)

    def draw(self, context):
        self._draw(self.layout, context)
        
    @staticmethod
    def _draw(layout, context):
        gcon = g(context)

        row = layout.row()
        row.template_list(
            'GIT_UL_file',
            '',
            gcon, "files",
            gcon, "active_file",
            # item_dyntip_propname="status",
            rows=2
            )
        col = row.column()
        col.menu("GIT_MT_file", icon='DOWNARROW_HLT', text="")


class GIT_MT_stash(Menu):
    bl_label = "Stash"

    def draw(self, context):
        layout = self.layout
        layout.operator("git.stash_apply", text="Apply", translate=False)
        layout.operator("git.stash_drop", text="Drop", translate=False)
        layout.operator("git.stash_clear", text="Clear", translate=False)


class GIT_PT_stash(GitPanel):
    bl_label = "Stash"

    def draw(self, context):
        self._draw(self.layout, context)
        
    @staticmethod
    def _draw(layout, context):
        gcon = g(context)
        if len(gcon.stashes)>0:
            row = layout.row()
            row.template_list(
                "UI_UL_list",
                "stashes",
                gcon,
                "stashes",
                gcon,
                "active_stash",
                rows=2
                )
            col = row.column()
            col.menu("GIT_MT_stash", icon='DOWNARROW_HLT', text="", translate=False)
        else:
            layout.label(text="No stashes.")

        layout.separator()

        if not gcon.is_dirty:
            alert(layout, "No local changes to save.")

        row = layout.row()
        row.operator("git.stash_save", text="Save Stash", icon='NEWFOLDER', translate=False)
        row.enabled = gcon.is_dirty


class GIT_UL_log(UIList):
    """For LogEntry"""

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        gcon = data
        log = item

        col = layout.column()
        for line in log.logline.split('\n'):
            col.label(text=line)

    def draw_filter(self, context, layout):
        row = layout.row()

        subrow = row.row(align=True)
        subrow.prop(self, "filter_name", text="")
        subrow.prop(self, "use_filter_invert", text="", icon='ARROW_LEFTRIGHT')

        subrow = row.row(align=True)
        prefs = p(context)
        subrow.prop_menu_enum(prefs, 'log_command', text="", icon='COLLAPSEMENU')



class GIT_MT_log(Menu):
    bl_label = "Log"

    def draw(self, context):
        gcon = context.window_manager.git_context
        layout = self.layout

        # prefs = p(context)
        # layout.prop_menu_enum(prefs, 'log_command', text="Log Command")
        # layout.separator()

        layout.operator("git.thumbnail_edit", icon='IMAGE_REFERENCE')
        layout.operator("git.checkout_file", icon='FILE_NEW')
        layout.operator("git.pick_library", icon='IMPORT')
        layout.separator()
        layout.operator("git.archive", icon='FILE_ARCHIVE')
        layout.operator("git.open_folder", text="Open Archive Folder", translate=False, icon='FILE_FOLDER').dirpath = common.get_archive_path(context)



class GIT_PT_log(GitPanel):
    bl_label = "Log"
    
    def draw(self, context):
        self._draw(self.layout, context)
        
    @staticmethod
    def _draw(layout, context):
        gcon = g(context)
        if len(gcon.logs)>0:
            row = layout.row()
            row.template_list(
                'GIT_UL_log',
                "logs",
                gcon, "logs",
                gcon, "active_log",
                item_dyntip_propname="name",
                sort_lock=True
                )
            col = row.column()
            col.operator("git.show", text="", icon='INFO')
            col.operator("git.reset", text="", icon='LOOP_BACK')
            col.operator("git.revert", text="", icon='FORWARD')
            col.menu("GIT_MT_log", icon='DOWNARROW_HLT', text="", translate=False)
        else:
            layout.label(text="No logs.")
        
        layout.separator()

        if not gcon.is_commit_ready:
            status = gcon.status
            if status & Git.STATUS_NOTSTAGED:
                alert(layout, "There are changes not staged for commit.")
            if status & Git.STATUS_UNTRACKED:
                alert(layout, "There are untracked files.")
            if status & Git.STATUS_UNMERGED:
                alert(layout, "There are unmerged files.")

        if not gcon.is_dirty:
            alert(layout, "Nothing to commit, working tree clean.")

        text = "Commit" if gcon.is_dirty else "Empty Commit"
        layout.operator("git.commit", text=text, icon='FOLDER_REDIRECT')



panels = (
    GIT_PT_context,
    GIT_PT_init,
    GIT_PT_shortcut,
    GIT_PT_branch,
    GIT_PT_file,
    GIT_PT_stash,
    GIT_PT_log
    )

classes = (
    GIT_PT_context,
    GIT_PT_init,
    GIT_PT_shortcut,

    GIT_MT_switch,
    GIT_MT_branch,
    GIT_PT_branch,

    GIT_MT_file,
    GIT_UL_file,
    GIT_PT_file,

    GIT_MT_stash,
    GIT_PT_stash,

    GIT_UL_log,
    GIT_MT_log,
    GIT_PT_log
    )