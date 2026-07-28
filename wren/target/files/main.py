"""Entry point for the ported CLI.

There's no single "main.c" among the uploaded files, but this plays the
role the original C `main()` would: it sets the process arguments (like
`osSetArguments()`), starts the REPL, and shuts everything down cleanly
(like `ioShutdown()` / `schedulerShutdown()`).
"""

import sys

from io_module import io_shutdown
from os_module import os_set_arguments
from scheduler_module import Scheduler
import repl_module


def main():
    os_set_arguments(sys.argv)

    try:
        repl_module.main()
    finally:
        # Originally: ioShutdown() + schedulerShutdown(), called on exit.
        io_shutdown()


if __name__ == "__main__":
    main()
