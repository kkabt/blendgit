import subprocess
import os
import platform

import sys
import re

from typing import Union, Generator



PTN_QUOTED = r"'(.*?)(?<!\\)'|\"(.*?)(?<!\\)\""
PTN_WORD = rf"([-\w\.=:]+({PTN_QUOTED})*)"

unquote = lambda w: re.sub(PTN_QUOTED, r"\1" or r"\2", w)


#git command class
class Git:
    PATH_GITIGNORE  = ".gitignore"
    
    # Status
    STATUS_UNMODIFIED   = 0b00000
    STATUS_IGNORED      = 0b00001
    STATUS_UNTRACKED    = 0b00010
    STATUS_UNMERGED     = 0b00100
    STATUS_NOTSTAGED    = 0b01000
    STATUS_STAGED       = 0b10000


    def __init__(self, context):
        prefs = context.preferences.addons[__package__].preferences
        path = prefs.git_execpath

        #try to use user supplied path first
        if path:
            self.git_execpath = path
        else: #try to autodetect
            if platform.architecture()[1] == "WindowsPE":
                #assume default git path for windows here, since we dont have winreg access via integrated python
                if platform.architecture()[0] == "64bit":
                    self.git_execpath = "C:/Program Files/Git/bin/git.exe"
                elif platform.architecture()[0] == "32bit":
                    self.git_execpath = "C:/Program Files (x86)/Git/bin/git.exe"
            else: #Linux, Mac
                self.git_execpath = "/usr/bin/git"

        self.operative = os.path.isfile(self.git_execpath)

        gcon = context.window_manager.git_context
        self.chdir(gcon.rootdir)


    # Update workdir file with specific version
    
    # def backup(self, filename, dirpath, commit_hash):
    def backup(self, blobnr, filepath):
        if blobnr!=None:
            p = subprocess.Popen(
                [self.git_execpath, "cat-file", "blob", blobnr],
                stdout = subprocess.PIPE, 
                stderr = subprocess.STDOUT
                )
            blob = p.stdout.read()

            with open(filepath, "wb+") as tmp:
                tmp.write(blob)
        return
    
    def get_blobs(self, commit_hash):
        blobs = {}
        results = self.command(["ls-tree", "-r", commit_hash])
        for l in results:
            tab = l.split("\t")
            name = tab[1]
            _,blob,blobnr = tab[0].split(" ")
            
            if blob=="blob":
                blobs[name] = blobnr
        return blobs


    # Miscellaneous
    
    def write_ignore(self, statement: str):
        with open(self.PATH_GITIGNORE, "a+") as f:
            f.write(statement+"\n")


    def clean_ignore(self):
        ignore_dict = {}
        with open(self.PATH_GITIGNORE, "r") as f:
            # fromkeys : remove overwrapping
            # reversed : statement priority is last written
            lines = list(dict.fromkeys([l.strip() for l in reversed(f.readlines())]))
            # reversed : restore order
            for line in reversed(lines):
                ignore_dict[line.lstrip("!")] = "!" if line.startswith("!") else ""

        with open(self.PATH_GITIGNORE, "w+") as f:
            f.writelines(
                [pattern+file+"\n" for file, pattern in ignore_dict.items()]
                )


    def chdir(self, dirpath) -> 'bool: Is path exist':
        if os.path.isdir(dirpath):
            os.chdir(dirpath)
            return True
        return False


    def open_dir(self, dirpath) -> 'exist: bool':
        if os.path.exists(dirpath):
            subprocess.Popen([
                'explorer',
                dirpath.replace("/", "\\")
                ])
            return True
        else:
            return False


    # generic Git command with [textual feedback]
    # => for interactive, get result as generator
          
    def command(self, cmd: Union[str, list, tuple]) -> Generator[str, None, bytes]:
        
        if not self.operative:
            return None
        
        args = [self.git_execpath]

        if type(cmd) is str:
            # (entire-matched, *other_groups) = findall
            args += [m[0] for m in re.findall(PTN_WORD, cmd)]
        elif type(cmd) in [list, tuple]:
            args += cmd
        else:
            print(f"TypeError: invalid argument type for 'cmd: Union[list, str]': {type(cmd)}", file=sys.stderr)
            return None

        # remove quote-character overwrapping
        args = list(map(unquote, args))
        # print(args)

        p = subprocess.Popen(
            args,
            stdout = subprocess.PIPE, 
            stderr = subprocess.STDOUT
            )

        while True:
            line = p.stdout.readline()
            if line:
                try:
                    out = line.decode('utf-8').rstrip('\n')
                    # print(out)
                    yield out
                except UnicodeDecodeError as e:
                    print(e)
                    out = line
                    yield out

            if not line and p.poll() is not None:
                break
