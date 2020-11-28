import os
import re


# common functions

get_git_context = lambda context: context.window_manager.git_context


get_addon_prefs = lambda context: context.preferences.addons[__package__].preferences


get_subpath = lambda *paths: os.path.join(os.path.dirname(__file__), *paths)


def extract_hash(text):
	PTN = r'(\*.*?|commit )\b(?P<commit_hash>[0-9a-f]{7,})\b'
	m = re.search(PTN, text)
	return m.group('commit_hash') if m else ""


def spaced_label(layout, text):
    layout.label(text=text.replace('\t', ' '*8))


def alert(layout, text):
    row = layout.row()
    row.alert = True
    row.label(text=text, icon='ERROR', translate=False)
    return row


def get_archive_path(context):
    gcon = get_git_context(context)
    prefs = get_addon_prefs(context)

    if prefs.archive_dir:
        # [archive_dir]/<project>
        dirpath = os.path.join([
            prefs.archive_dir,
            bpy.path.basename(gcon.rootdir),
            ])
    else:
        # <project>/archive
        dirpath = os.path.join(gcon.rootdir, "archive")

    return dirpath


__all__ = []