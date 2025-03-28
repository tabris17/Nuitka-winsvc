#     Copyright 2025, Kay Hayen, mailto:kay.hayen@gmail.com find license text at end of file


""" Distutils example that contains only plain module.

"""

from setuptools import setup

# use `python setup.py bdist_nuitka` to use nuitka or use
# in the setup(..., build_with_nuitka=True, ...)
# and bdist and build will always use nuitka

setup(
    name="py_modules_only",
    description="nuitka bdist_nuitka test-case compiling py_modules only" + " package",
    author="Nobody really",
    author_email="email@someplace.com",
    py_modules=["py_modules_only"],
    version="0.1",
    scripts=["runner"],
)

#     Python test originally created or extracted from other peoples work. The
#     parts from me are licensed as below. It is at least Free Software where
#     it's copied from other people. In these cases, that will normally be
#     indicated.
#
#     Licensed under the Apache License, Version 2.0 (the "License");
#     you may not use this file except in compliance with the License.
#     You may obtain a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#     Unless required by applicable law or agreed to in writing, software
#     distributed under the License is distributed on an "AS IS" BASIS,
#     WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#     See the License for the specific language governing permissions and
#     limitations under the License.
