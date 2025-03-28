#!/usr/bin/env python
#     Copyright 2025, Kay Hayen, mailto:kay.hayen@gmail.com find license text at end of file


""" Launcher for git hook installer tool.

"""

import os
import sys

# Unchanged, running from checkout, use the parent directory, the nuitka
# package ought be there.
sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "..")))

# isort:start

import stat

from nuitka.tools.Basics import goHome
from nuitka.Tracing import tools_logger
from nuitka.utils.Execution import getExecutablePath
from nuitka.utils.FileOperations import (
    getFileContents,
    getWindowsShortPathName,
)


def main():
    goHome()

    if os.name == "nt":
        git_path = getExecutablePath("git")

        if git_path is None:
            git_path = r"C:\Program Files\Git\bin\sh.exe"

            if not os.path.exists(git_path):
                git_path = None

        if git_path is None:
            tools_logger.sysexit(
                """\
Error, cannot locate 'git.exe' which we need to install git hooks. Add it to
PATH while executing this will be sufficient."""
            )

        for candidate in (
            "sh.exe",
            os.path.join("..", "bin", "sh.exe"),
            os.path.join("..", "..", "bin", "sh.exe"),
        ):
            sh_path = os.path.normpath(
                os.path.join(os.path.dirname(git_path), candidate)
            )

            if os.path.exists(sh_path):
                break
        else:
            tools_logger.sysexit(
                """\
Error, cannot locate 'sh.exe' near 'git.exe' which we need to install git hooks,
please improve this script."""
            )

        # For MinGW and #! we will need a path without spaces, so use this
        # code to find the short name, that won't have it.
        sh_path = getWindowsShortPathName(sh_path)

    for hook in os.listdir(".githooks"):
        full_path = os.path.join(".githooks", hook)

        hook_contents = getFileContents(full_path)

        if hook_contents.startswith("#!/bin/sh"):
            if os.name == "nt":
                # Correct shebang for Windows git to work.
                hook_contents = "#!%s\n%s" % (
                    sh_path.replace("\\", "/").replace(" ", r"\ "),
                    hook_contents[10:],
                )

            # Also use "sys.executable" to make sure we find auto-format tool.
            hook_contents = hook_contents.replace(
                "./bin/autoformat-nuitka-source",
                "'%s' ./bin/autoformat-nuitka-source" % sys.executable,
            )
        else:
            sys.exit("Error, unknown hook contents.")

        hook_target = os.path.join(".git/hooks/", hook)
        with open(hook_target, "wb") as out_file:
            out_file.write(hook_contents.encode("utf8"))

        st = os.stat(hook_target)
        os.chmod(hook_target, st.st_mode | stat.S_IEXEC)


if __name__ == "__main__":
    main()

#     Part of "Nuitka", an optimizing Python compiler that is compatible and
#     integrates with CPython, but also works on its own.
#
#     Licensed under the Apache License, Version 2.0 (the "License");
#     you may not use this file except in compliance with the License.
#     You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#     Unless required by applicable law or agreed to in writing, software
#     distributed under the License is distributed on an "AS IS" BASIS,
#     WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#     See the License for the specific language governing permissions and
#     limitations under the License.
