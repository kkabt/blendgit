import bpy
from bpy.types import Operator
from bpy.props import *

from threading import Thread
import os

from .backend_git import Git
from . import common
from .common import (
    alert,
    get_git_context as g,
    get_addon_prefs as p
    )


# +++++++++++++++++++++++++++++++++++++++++++++
# 
#   Functions
# 
# +++++++++++++++++++++++++++++++++++++++++++++

def __reload_entries(context, name, cmd):
    results = Git(context).command(cmd)

    entries = getattr(g(context), name)
    entries.clear()
    for line in results:
        entries.add().logline = line


def reload_files(context):
    __reload_entries(context, 'files', ["status", "-s", "--ignored"])

    # reload unmodified files
    gcon = g(context)
    results = Git(context).command(["ls-files", "-c"])
    files = [f.ref for f in gcon.files]
    for file in results:
        if file not in files:
            gcon.files.add().logline = "H  " + file


def reload_branches(context):
    __reload_entries(context, 'branches', ["branch"])


def reload_stashes(context):
    __reload_entries(context, 'stashes', ["stash", "list"])


def reload_logs(context):
    # update logs
    prefs = p(context)
    cmd = prefs.log_command or "log --graph --oneline --all"
    __reload_entries(context, 'logs', cmd)

    # combine multilines
    gcon = g(context)
    for i, log in enumerate(gcon.logs):
        while True:
            idx = i+1
            if idx >= len(gcon.logs):
                break
            log_next = gcon.logs[idx]
            if idx == 0 or log_next.commit_hash:
                break
            log.logline += "\n" + log_next.logline
            gcon.logs.remove(idx)
        
    for log in gcon.logs:
        update_thumbnail(context, log)

    gcon.active_log = 0


def get_thumbnail_path(context, commit_hash):
    gcon = g(context)
    path = os.path.join(
        gcon.rootdir,
        ".git",
        ".git_thumbnails",
        f"{commit_hash}.png"
        )
    return path


def update_thumbnail(context, log):
    name = "." + log.commit_hash

    if log.thumbnail is None:
        textures = bpy.data.textures
        tex = textures.get(name)
        log.thumbnail = tex or textures.new(name, 'IMAGE')
    img = log.thumbnail.image or bpy.data.images.get(name)
    if img:
        img.reload()
        log.thumbnail.image = img
    else:
        path = get_thumbnail_path(context, log.commit_hash)
        if os.path.isfile(path):
            img = bpy.data.images.load(path)
            img.name = name
            log.image = img
            
            log.thumbnail.image = img
            log.thumbnail.extension = 'CLIP'

    if img:
        w, h = img.size
        if w * h:
            if w > h:
                log.thumbnail.crop_max_x = h / w
            else:
                log.thumbnail.crop_max_y = w / h


# +++++++++++++++++++++++++++++++++++++++++++++
# 
#   OPERATORS
# 
# +++++++++++++++++++++++++++++++++++++++++++++

# GitOperator
# GIT_OT_reload
# GIT_OT_load
# GIT_OT_init

# BranchOperator
# GIT_OT_branch
# GIT_OT_switch
# GIT_OT_merge

# FileOperator
# GIT_OT_stage
# GIT_OT_unstage
# GIT_OT_untrack
# GIT_OT_ignore
# GIT_OT_notice

# StashOperator
# GIT_OT_stash

# LogOperator
# GIT_OT_reset
# GIT_OT_revert
# GIT_OT_commit


class GitOperator(Operator):
    bl_options = {'INTERNAL'}

    popup_options = bl_options | {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        cls.check_repo(context)
        return cls.__git.operative

    @classmethod
    def check_repo(cls, context):
        cls.__git_context   = gcon  = g(context)
        cls.__git           = git   = Git(context)
        if not git.operative:
            print(cls.__name__, __name__, "Git is NOT operative")
        return git.operative and gcon.is_repository

    __git_context = None
    __entry = None

    __git = None
    __results = None
    __result_string = ""

    @property
    def git(self):
        return self.__git

    @classmethod
    def get_entry(cls):
        return cls.__entry

    @classmethod
    def set_entry(cls, prop_coll, prop_int):
        gcon = cls.__git_context
        entries = getattr(gcon, prop_coll)
        active = getattr(gcon, prop_int)

        if len(entries) > active:
            cls.__entry = entries[active]
        else:
            cls.__entry = None

        return bool(cls.__entry)

    @classmethod
    def command(cls, cmd, reporter=None):
        cls.__results = cls.__git.command(cmd)
        cls.__result_string = ""
        if hasattr(reporter, 'report'):
            res = cls.get_results(str)
            if res.strip():
                if 'fatal' in res:
                    t = {'ERROR'}
                elif res == 'No local changes to save':
                    t = {'WARNING'}
                else:
                    t = {'INFO'}
                reporter.report(t, res)

    @classmethod
    def get_results(cls, type=None):
        if type is None:
            return cls.__results
        elif type is str:
            if not cls.__result_string and cls.__results:
                cls.__result_string = "\n".join(list(cls.__results))
            return cls.__result_string
        else:
            return None


class GIT_OT_reload(GitOperator):
    bl_idname = "git.reload"
    bl_label = "Reload Repository"
    bl_description = "Reload current repository"

    def invoke(self, context, event):
        gcon = g(context)

        # check version
        self.command(["version"])
        gcon.version = self.get_results(str)

        # check: is cwd repository?
        exist = self.git.chdir(gcon.rootdir)
        if exist:
            self.command(["rev-parse", "--show-toplevel"])

            err_str = 'fatal: not a git repository'
            gcon.is_repository = err_str not in self.get_results(str)

            if gcon.is_repository:
                gcon.rootdir = self.get_results(str)
                self.git.chdir(gcon.rootdir)
        else:
            gcon.is_repository = False

        if not gcon.is_repository:
            gcon.rootdir = ""
            self.report({'WARNING'}, "Not a git repository")
            return {'CANCELLED'}

        return self.execute(context)


    def execute(self, context):
        threads = (
            Thread(target=t, args=(context,))
            for t in (
                reload_files,
                reload_branches,
                reload_stashes,
                reload_logs
                )
            )
        for t in threads:
            t.start()

        self.git.clean_ignore()

        for t in threads:
            t.join()

        self.report({'INFO'}, "Reloaded repository.")
        return {'FINISHED'}


class GIT_OT_load(GitOperator):
    bl_idname = "git.load"
    bl_label = "Load Repository"

    directory: StringProperty(subtype='DIR_PATH')
    unload: BoolProperty()

    @classmethod
    def description(cls, context, properties):
        if properties.unload:
            return "Unload repository from current context"
        else:
            return "Load repository to current context"

    def invoke(self, context, event):
        gcon = g(context)
        if self.unload and gcon.is_repository:
            gcon.rootdir = ""
            gcon.is_repository = False
            self.report({'INFO'}, "Unload repository")
            return {'FINISHED'}

        if not gcon.is_repository:
            self.directory = bpy.path.abspath("//") or self.directory
            context.window_manager.fileselect_add(self)
            return {'RUNNING_MODAL'}

        return {'CANCELLED'}

    def execute(self, context):
        if os.path.isdir(self.directory):
            gcon = g(context)
            gcon.rootdir = self.directory

            bpy.ops.git.reload('INVOKE_DEFAULT')

            self.report({'INFO'}, f"Load repository: {self.directory}")
            return {'FINISHED'}

        else:
            self.report({'ERROR'}, "Selected path is not exist")
            return {'CANCELLED'}


class GIT_OT_init(GitOperator):
    bl_idname = "git.init"
    bl_label = "Initialize Repository"
    bl_description = "$git init"

    directory: StringProperty(subtype='DIR_PATH')

    @classmethod
    def poll(cls, context):
        gcon = g(context)
        return super().poll(context) and not gcon.is_repository

    def invoke(self, context, event):
        self.directory = bpy.path.abspath("//")
        if self.directory:
            return self.execute(context)

        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        gcon = g(context)

        exist = self.git.chdir(self.directory)
        if not exist:
            self.report({'ERROR'}, "Selected path is not exist")
            return {'CANCELLED'}

        self.command(["rev-parse", "--show-toplevel"])
        if 'fatal' not in self.get_results(str):
            self.report({'ERROR'}, "Selected directory is already repository")
            self.git.chdir(gcon.rootdir)
            return {'CANCELLED'}

        gcon.rootdir = self.directory

        self.command(["init"], reporter=self)

        self.git.write_ignore(Git.PATH_GITIGNORE)
        bpy.ops.git.reload('INVOKE_DEFAULT')

        self.report({'INFO'}, f"Initialize repository: {self.directory}")
        return {'FINISHED'}



class BranchOperator(GitOperator):
    @classmethod
    def poll(cls, context):
        return (
            cls.check_repo(context)
            and cls.set_entry('branches', 'active_branch')
            and len(g(context).branches) >= cls.need_branches
            )

    need_branches = 2

    @classmethod
    def branch_items_fn(cls, context, exclude_self=True):
        gcon = g(context)
        if exclude_self:
            current = gcon.branches[gcon.active_branch]
            cond = lambda branch: branch.name!=current.name
        else:
            cond = lambda branch: True
        return [(br.name, br.name, "") for br in gcon.branches if cond(br)]


class GIT_OT_branch_add(BranchOperator):
    bl_idname = "git.branch_add"
    bl_label = "Add Branch"
    bl_description = "$git branch <branchname>"

    name: StringProperty()

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def execute(self, context):
        self.command(["branch", self.name], reporter=self)

        reload_branches(context)
        reload_logs(context)
        return {'FINISHED'}


class GIT_OT_branch_rename(BranchOperator):
    bl_idname = "git.branch_rename"
    bl_label = "Rename Branch"
    bl_description = "$git branch (-m | -M) <oldbranch> <newbranch>"

    branch: EnumProperty(name="Old Branch", items=lambda s,c: __class__.branch_items_fn(c, exclude_self=False))
    name: StringProperty(name="New Branch")
    is_force: BoolProperty(name="Force")

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def execute(self, context):
        self.command([
                "branch",
                "-M" if self.is_force else "-m",
                self.branch,
                self.name
            ],
            reporter=self
            )

        reload_branches(context)
        reload_logs(context)
        return {'FINISHED'}


class GIT_OT_branch_copy(BranchOperator):
    bl_idname = "git.branch_copy"
    bl_label = "Copy Branch"
    bl_description = "$git branch (-c | -C) <oldbranch> <newbranch>"

    branch: EnumProperty(name="Old Branch", items=lambda s,c: __class__.branch_items_fn(c, exclude_self=False))
    name: StringProperty(name="New Branch")
    is_force: BoolProperty(name="Force")

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def execute(self, context):
        self.command([
                "branch",
                "-C" if self.is_force else "-c",
                self.branch,
                self.name
            ],
            reporter=self
            )

        reload_branches(context)
        reload_logs(context)
        return {'FINISHED'}


class GIT_OT_branch_delete(BranchOperator):
    bl_idname = "git.branch_delete"
    bl_label = "Delete Branch"
    bl_description = "$git branch (-d | -D) <branchname>"

    branch: EnumProperty(name="Old Branch", items=lambda s,c: __class__.branch_items_fn(c))
    is_force: BoolProperty(name="Force")

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def execute(self, context):
        self.command([
                "branch",
                "-D" if self.is_force else "-d",
                self.branch
            ],
            reporter=self
            )

        reload_branches(context)
        reload_logs(context)
        return {'FINISHED'}


class GIT_OT_switch(BranchOperator):
    bl_idname = "git.switch"
    bl_label = "File is dirty: Recent edits are to be discarded"
    bl_description = "$git switch <branch>"
    
    need_branches = 2

    branchname: StringProperty(options={'HIDDEN'})

    @classmethod
    def poll(cls, context):
        return super().poll(context) and not g(context).is_dirty

    def invoke(self, context, event):
        if bpy.data.is_dirty:
            wm = context.window_manager
            return wm.invoke_confirm(self, event)
        return self.execute(context)

    def execute(self, context):
        if self.branchname:
            self.command(["switch", self.branchname], reporter=self)
            if "error" in self.get_results(str):
                return {'CANCELLED'}
            bpy.ops.wm.revert_mainfile()
            return {'FINISHED'}


class GIT_OT_merge(BranchOperator):
    bl_idname = "git.merge"
    bl_label = "Merge Branch"
    bl_description = "$git merge [--ff | --no-ff | --squash] [-Xours | -Xtheirs] <branch>"

    need_branches = 2

    incoming_branch: EnumProperty(
        items=lambda s,c: __class__.branch_items_fn(c),
        name="Incoming Branch"
        )

    ff_count: IntProperty()
    fastforward: EnumProperty(
        items=[
            ('--ff', "--ff", ""),
            ('--no-ff', "--no-ff", ""),
            # ('--ff-only', "--ff-only", ""),
            ('--squash', "--squash", "")
            ],
        default='--no-ff',
        name="Fast-Forward"
        )

    is_conflict: BoolProperty()
    strategy: EnumProperty(
        name="Strategy",
        items=[
            # ('--abort', "--abort", "In case of conflict, abort merge"),
            ('-Xours', "-Xours", "In case of conflict, prefer merged-in branch changes"),
            ('-Xtheirs', "-Xtheirs", "In case of conflict, prefer target branch changes"),
            ],
        default='-Xours',
        )

    message: StringProperty()

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        if bpy.data.is_dirty:
            layout.label(text="Dirty: Recent edits have NOT been saved to disk.", icon='ERROR')
            layout.separator()

        layout.prop(self, 'incoming_branch')

        layout.separator()
        layout.prop(self, 'fastforward', expand=True)

        layout.separator()
        layout.prop(self, 'strategy', expand=True)

        layout.separator()
        layout.prop(self, 'message', text="Message")

    def execute(self, context):
        cmd = ["merge", self.incoming_branch]

        if self.ff_count == 0:
            cmd.append(self.fastforward)

        if self.is_conflict:
            cmd.append(self.strategy)

        if self.message:
            cmd.extend(["-m", self.message])

        self.command(cmd, reporter=self)

        # if self.strategy == '--squash':
        #     self.command(["commit"])
        
        bpy.ops.wm.revert_mainfile()
        return {'FINISHED'}


class FileOperator(GitOperator):
    @classmethod
    def poll(cls, context):
        return cls.check_repo(context)


class GIT_OT_stage(FileOperator):
    bl_idname = "git.stage"
    bl_label = "Stage File"
    bl_description = "$git add [<pathspec>...]"

    target_ref: StringProperty()

    def execute(self, context):
        self.command(["add", self.target_ref], reporter=self)

        reload_files(context)
        return {'FINISHED'}


class GIT_OT_unstage(FileOperator):
    bl_idname = "git.unstage"
    bl_label = "Unstage File"

    target_ref: StringProperty()
    resolve_unmerge: BoolProperty()

    @classmethod
    def description(cls, context, properties):
        opt = "--theirs" if properties.resolve_unmerge else "--staged"
        return f"$git restore {opt} {properties.target_ref}"

    def execute(self, context):
        opt = "--theirs" if self.resolve_unmerge else "--staged"

        self.command(["restore", opt, self.target_ref], reporter=self)

        reload_files(context)
        return {'FINISHED'}


class GIT_OT_untrack(FileOperator):
    bl_idname = "git.untrack"
    bl_label = "Untrack File"
    bl_description = "$git rm --cached [<pathspec>...]"

    target_ref: StringProperty()

    def execute(self, context):
        self.command(["rm", "--cached", self.target_ref], reporter=self)

        reload_files(context)
        return {'FINISHED'}


class GIT_OT_ignore(FileOperator):
    bl_idname = "git.ignore"
    bl_label = "Ignore File"
    bl_description = "Set selected file ignored"

    target_ref: StringProperty()

    def execute(self, context):
        self.git.write_ignore(self.target_ref)

        reload_files(context)
        return {'FINISHED'}


class GIT_OT_notice(FileOperator):
    bl_idname = "git.notice"
    bl_label = "Notice File"
    bl_description = "Unset selected file ignored"

    target_ref: StringProperty()

    def execute(self, context):
        self.git.write_ignore("!"+self.target_ref)

        reload_files(context)
        return {'FINISHED'}


class StashOperator(GitOperator):
    @classmethod
    def poll(cls, context):
        return cls.check_repo(context) and cls.set_entry('stashes', 'active_stash')


class GIT_OT_stash_save(StashOperator):
    bl_idname = "git.stash_save"
    bl_label = "Save Stash"
    bl_description = "$git stash save <msg> -u"

    message: StringProperty(name="Message")
    include_untracked: BoolProperty()

    @classmethod
    def poll(cls, context):
        return cls.check_repo(context) and g(context).is_dirty

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self, width=400)

    def draw(self, context):
        layout = self.layout
        if g(context).status & Git.STATUS_UNTRACKED:
            alert(layout, "There are untracked files.")
            layout.prop(self, 'include_untracked', text="Include Untracked")
        layout.prop(self, 'message')

    def execute(self, context):
        cmd = ["stash", "save", self.message, "-u"]
        self.command(cmd, reporter=self)

        bpy.ops.wm.revert_mainfile()
        return {'FINISHED'}


class GIT_OT_stash_apply(StashOperator):
    bl_idname = "git.stash_apply"
    bl_label = "Apply Stash"
    bl_description = "$git stash apply <stash>"

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_confirm(self, event)

    def execute(self, context):
        cmd = ["stash", "apply", self.get_entry().revision]
        self.command(cmd, reporter=self)

        bpy.ops.wm.revert_mainfile()
        return {'FINISHED'}


class GIT_OT_stash_drop(StashOperator):
    bl_idname = "git.stash_drop"
    bl_label = "Drop Stash"
    bl_description = "$git stash drop <stash>"

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_confirm(self, event)

    def execute(self, context):
        cmd = ["stash", "drop", self.get_entry().revision]
        self.command(cmd, reporter=self)
        reload_stashes(context)
        reload_logs(context)
        return {'FINISHED'}


class GIT_OT_stash_clear(StashOperator):
    bl_idname = "git.stash_clear"
    bl_label = "Clear Stash"
    bl_description = "$git stash clear"

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_confirm(self, event)

    def execute(self, context):
        cmd = ["stash", "clear"]
        self.command(cmd, reporter=self)
        reload_stashes(context)
        reload_logs(context)
        return {'FINISHED'}


class LogOperator(GitOperator):
    @classmethod
    def poll(cls, context):
        if cls.check_repo(context):
            cls.set_entry('logs', 'active_log')
            log = cls.get_entry()
            return log and log.commit_hash
        else:
            return False


class GIT_OT_reset(LogOperator):
    bl_idname = "git.reset"
    bl_label = "Reset Commit"
    bl_description = "$git reset [--soft | --mixed | --hard] <commit>"
    
    option: EnumProperty(
        items=[
            ('--soft', "--soft", ""),
            ('--mixed', "--mixed", ""),
            ('--hard', "--hard", ""),
            ],
        default="--mixed"
        )

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        if bpy.data.is_dirty:
            layout.label(text="Dirty: Recent edits have NOT been saved to disk.", icon='ERROR')
            layout.separator()
        layout.prop(self, "option", text = "Option", expand = True, translate = False)

    def execute(self, context):
        c_hash = self.get_entry().commit_hash
        if c_hash == "":
            return {'CANCELLED'}

        self.command([
            "reset",
            self.option,
            c_hash
            ],
            reporter=self
            )

        bpy.ops.wm.revert_mainfile()
        return {'FINISHED'}


class GIT_OT_revert(LogOperator):
    bl_idname = "git.revert"
    bl_label = "Revert Commit"
    bl_description = "$git revert [--no-edit] <commit>"

    def parent_items_fn(self, context):
        cls = GIT_OT_revert
        cls.command(["show", cls.get_entry().commit_hash])
        for line in cls.get_results():
            if line.startswith("Merge:"):
                _, c1, c2 = line.split(' ')
                return [
                    ('1', c1, ""),
                    ('2', c2, "")
                    ]
        return None

    parent: EnumProperty(items=parent_items_fn)

    def __init__(self):
        is_merge = False

    def invoke(self, context, event):
        # git = Git(context)
        # results = git.command(["show", self.c_hash])
        # self.is_merge = "Merge: " in self.get_results(str)
        self.is_merge = bool(self.parent)

        wm = context.window_manager
        if self.is_merge or bpy.data.is_dirty:
            return wm.invoke_props_dialog(self)

        return wm.invoke_confirm(self, event)

    def draw(self, context):
        layout = self.layout
        if bpy.data.is_dirty:
            layout.label(text="Dirty: Recent edits have NOT been saved to disk.", icon='ERROR')
            layout.separator()
        if self.is_merge:
            layout.label(text=self.get_entry().commit_hash+" is merge commit.")
            layout.prop(self, 'parent', expand=True, translate = False)

    def execute(self, context):
        cmd = ["revert", self.get_entry().commit_hash, "--no-edit"]
        if self.is_merge:
            cmd += ["-m", self.parent]

        self.command(cmd, reporter=self)

        bpy.ops.wm.revert_mainfile()
        return {'FINISHED'}


# class GIT_OT_rebase(LogOperator):
#     bl_idname = "git.rebase"
#     bl_label = "Rebase Commit"
#     bl_description = "$git rebase <commit>"

#     def invoke(self, context, event):
#         return self.execute(context)

#     def execute(self, context, event):
#         return {'FINISHED'}


# class GIT_OT_cherry_pick(LogOperator):
#     bl_idname = "git.cherry_pick"
#     bl_label = "Cherry-pick Commit"
#     bl_description = "$git cherry-pick <commit>"

#     def execute(self, context):
#         log = self.get_entry()
#         self.command(
#             ["cherry-pick", "-n", log.commit_hash],
#             reporter=self
#             )
#         return {'FINISHED'}


class GIT_OT_commit(LogOperator):
    bl_idname = "git.commit"
    bl_label = "Commit"
    bl_description = "$git commit -m <msg>"

    # 3 line format: summary, blank, desc
    summary: StringProperty(name="Summary")
    desc: StringProperty(name="Description")
        
    @classmethod
    def poll(cls, context):
        return cls.check_repo(context) and g(context).is_commit_ready

    def invoke(self, context, event):
        self.summary = self.desc = ""

        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        if not g(context).is_dirty:
            alert(layout, "This is empty commit")
            layout.separator()

        layout.label(text="Summary")
        row = layout.row()
        row.prop(self, "summary", text="")

        layout.label(text="Description")
        layout.prop(self, "desc", text="")


    def execute(self, context):
        if not self.summary and not self.desc:
            self.report({'ERROR'}, "Comment is empty")
            return {'CANCELLED'}

        comment = self.summary + "\n\n" + self.desc

        cmd = ["commit", "-m", comment]

        if not g(context).is_dirty:
            cmd.append("--allow-empty")

        self.command(
            cmd,
            reporter=self
            )

        bpy.ops.git.reload('INVOKE_DEFAULT')
        return {'FINISHED'}



classes = (
    # GitOperator
    GIT_OT_reload,
    GIT_OT_load,
    GIT_OT_init,

    # BranchOperator
    GIT_OT_branch_add,
    GIT_OT_branch_rename,
    GIT_OT_branch_copy,
    GIT_OT_branch_delete,
    GIT_OT_switch,
    GIT_OT_merge,

    # FileOperator
    GIT_OT_stage,
    GIT_OT_unstage,
    GIT_OT_untrack,
    GIT_OT_ignore,
    GIT_OT_notice,

    # StashOperator
    GIT_OT_stash_save,
    GIT_OT_stash_apply,
    GIT_OT_stash_drop,
    GIT_OT_stash_clear,

    # LogOperator
    GIT_OT_reset,
    GIT_OT_revert,
    # GIT_OT_rebase,
    # GIT_OT_cherry_pick,
    GIT_OT_commit
    )