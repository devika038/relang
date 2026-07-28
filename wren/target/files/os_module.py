"""Ported from os.h, os.c, and os.wren.

The original C file used libuv (uv_os_homedir, uv_os_getpid, etc.) and the
Wren embedding API to expose `Platform` and `Process` foreign classes to
Wren scripts. This port keeps the same two classes and the same method
names, implemented directly with Python's standard library.
"""

import os
import sys

# Originally: WREN_PATH_MAX in os.h. Kept for parity even though Python's
# os.path.expanduser has no fixed buffer size limit.
WREN_PATH_MAX = 4096

# Originally: numArgs / args globals in os.c, set by osSetArguments().
_num_args = 0
_args = []


def os_set_arguments(argv):
    """Stores the command line arguments passed to the CLI.

    Originally: osSetArguments(int argc, const char* argv[]) in os.c/os.h.
    """
    global _num_args, _args
    _args = list(argv)
    _num_args = len(_args)


class Platform:
    """Ported from `Platform` in os.wren, and platformHomePath() /
    platformName() / platformIsPosix() in os.c.
    """

    @staticmethod
    def home_path():
        # Originally: platformHomePath() -> uv_os_homedir().
        home = os.path.expanduser("~")
        if home == "~":
            raise RuntimeError("Cannot get the current user's home directory.")
        return home

    @staticmethod
    def name():
        # Originally: platformName().
        if sys.platform.startswith("win"):
            return "Windows"
        elif sys.platform == "darwin":
            # Originally distinguished iOS vs OS X via TargetConditionals.h;
            # not meaningful for a desktop Python interpreter, so this
            # always reports "OS X" the way the original CLI build did.
            return "OS X"
        elif sys.platform.startswith("linux"):
            return "Linux"
        elif os.name == "posix":
            return "Unix"
        else:
            return "Unknown"

    @staticmethod
    def is_posix():
        # Originally: platformIsPosix().
        return os.name == "posix"

    @staticmethod
    def is_windows():
        # Originally: `static isWindows { name == "Windows" }` in os.wren.
        return Platform.name() == "Windows"


class Process:
    """Ported from `Process` in os.wren, and processAllArguments() /
    processCwd() / processPid() / processPpid() / processVersion() in os.c.
    """

    @staticmethod
    def all_arguments():
        # Originally: processAllArguments().
        return list(_args)

    @staticmethod
    def arguments():
        # Originally:
        #   static arguments { allArguments.count >= 2 ? allArguments[2..-1] : [] }
        # TODO: This will need to be smarter when wren supports CLI options.
        all_args = Process.all_arguments()
        return all_args[2:] if len(all_args) >= 2 else []

    @staticmethod
    def cwd():
        # Originally: processCwd() -> uv_cwd().
        try:
            return os.getcwd()
        except OSError as error:
            raise RuntimeError("Cannot get current working directory.") from error

    @staticmethod
    def pid():
        # Originally: processPid() -> uv_os_getpid().
        return os.getpid()

    @staticmethod
    def ppid():
        # Originally: processPpid() -> uv_os_getppid().
        return os.getppid()

    @staticmethod
    def version():
        # Originally: processVersion() -> WREN_VERSION_STRING.
        return "wren-cli (python port)"
