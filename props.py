import bpy
from bpy.types import PropertyGroup
from bpy.props import *

from functools import reduce

from .backend_git import Git
from .common import extract_hash


class BranchEntry(PropertyGroup):
    def __update(self, context):
        self.name = self.logline[2:]

    logline: StringProperty(update=__update)


class FileEntry(PropertyGroup):
    def __update(self, context):
        logline = self.logline

        self.name = logline
        self.ref = logline[3:].strip('"')

        X,Y = logline[:2]

        if X+Y=="!!":  # ignored
            status = Git.STATUS_IGNORED
        elif X+Y=="??":  # untracked
            status = Git.STATUS_UNTRACKED
        elif X+Y in [  # merge conflicts
            "DD",   # unmerged, both deleted
            "AU",   # unmerged, added by us
            "UD",   # unmerged, deleted by them
            "UA",   # unmerged, added by them
            "DU",   # unmerged, deleted by us
            "AA",   # unmerged, both added
            "UU"    # unmerged, both modified
            ]:
            status = Git.STATUS_UNMERGED
        elif Y in "AMDRC":  # not updated
            status = Git.STATUS_NOTSTAGED
        elif X in "DMARC":  # index and worktree matches
            status = Git.STATUS_STAGED
        elif X == "H":      # unmodified(ls-files)
            status = Git.STATUS_UNMODIFIED

        self.status = status

    logline: StringProperty(update=__update)
    ref: StringProperty()
    status: IntProperty(
        min=Git.STATUS_UNMODIFIED,
        max=Git.STATUS_STAGED
        )


class StashEntry(PropertyGroup):

    def __update(self, context):
        logline = self.logline

        self.name = logline
        self.revision, self.branch, self.message = logline.split(': ', 2)

    logline: StringProperty(update=__update)

    revision: StringProperty()
    branch: StringProperty()  # WIP on / On
    message: StringProperty()


class LogEntry(PropertyGroup):

    def __update(self, context):
        logline = self.logline
        self.name = logline

        c_hash = extract_hash(logline)
        if c_hash:
            self.commit_hash = c_hash

    logline: StringProperty(update=__update)
    commit_hash: StringProperty()

    thumbnail: PointerProperty(type=bpy.types.ImageTexture)


class GitContext(PropertyGroup):
    version: StringProperty()
    rootdir: StringProperty(subtype='DIR_PATH')
    is_repository: BoolProperty()

    status: IntProperty(
        get=lambda self: reduce(lambda a,u: a|u, [f.status for f in self.files]) if self.files else Git.STATUS_IGNORED
        )
    is_dirty: BoolProperty(get=lambda s: bool(s.status>>1))
    is_commit_ready: BoolProperty(
        get=lambda self: not (self.status & (
            Git.STATUS_UNTRACKED
            | Git.STATUS_UNMERGED
            | Git.STATUS_NOTSTAGED
            ))
        )
    
    active_branch: IntProperty(
        get=lambda self: [i for i,br in enumerate(self.branches) if br.logline.startswith("*")][0]
        )
    branches: CollectionProperty(type=BranchEntry)

    active_file: IntProperty()
    files: CollectionProperty(type=FileEntry)

    active_stash: IntProperty()
    stashes: CollectionProperty(type=StashEntry)

    active_log: IntProperty()
    logs: CollectionProperty(type=LogEntry)

    def log_from_hash(self, commit_hash):
        key = lambda l: l.commit_hash in commit_hash
        match = list(filter(key, self.logs))
        return match[0] if match else None



classes = (
    BranchEntry,
    FileEntry,
    StashEntry,
    LogEntry,
    GitContext
    )

def register():
    if not hasattr(bpy.types.WindowManager, 'git_context'):
        setattr(bpy.types.WindowManager, 'git_context', PointerProperty(type=GitContext))

def unregister():
    if hasattr(bpy.types.WindowManager, 'git_context'):
        delattr(bpy.types.WindowManager, 'git_context')