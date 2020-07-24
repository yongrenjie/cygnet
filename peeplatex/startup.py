"""
main.py
-------

Contains functions that need to be run at startup. The entry point to the
command-line interface is main().
"""

import os
import sys
import asyncio
import argparse
import re
from pathlib import Path
from enum import Enum
from datetime import datetime, timezone

import yaml
import aiohttp
import prompt_toolkit as pt

from . import prompt
from . import fileio
from . import backup
from . import commands
from ._shared import *


def main():
    """
    Entry point for the program. Perform startup tasks, then run the
    main coroutine.
    """
    # Parse sys.argv
    parser = argparse.ArgumentParser()
    parser.add_argument("path",
                        help=("Path to start PeepLaTeX in. "
                              "Defaults to current working directory."),
                        nargs='?',
                        default=Path.cwd())
    # In the future we will change this to --debug, but I want all the
    # debugging stuff while this is still in development.
    parser.add_argument("--nodebug", help="Disable debugging output",
                        action="store_true")
    args = parser.parse_args()
    _g.debug = not args.nodebug
    if _g.debug:
        _debug("Debugging mode enabled.")

    # Startup.
    dir = Path(args.path).resolve().expanduser()
    if dir.is_dir():
        # Set current path
        _g.currentPath = dir
        # Try to load the db.yaml file, if it exists
        try:
            _g.articleList = fileio.read_articles(dir)
        except FileNotFoundError:
            pass
        except yaml.YAMLError:
            _error(f"A db.yaml file was found in {dir}, "
                   "but it contained invalid YAML.")
        else:
            backup.createBackup()
        # Resize terminal
        cols, rows = os.get_terminal_size()
        cols = max(cols, 175)
        rows = max(rows, 50)
        sys.stdout.write(f"\x1b[8;{rows};{cols}t")
        # Run main coroutine until complete
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main_coro())
        loop.close()
    else:
        _error(f"PeepLaTeX: directory {args.path} does not exist")



async def main_coro():
    """
    Main coroutine.
    """
    # Start autosave task
    t_autosave = asyncio.create_task(backup.autosave())

    # Launch aiohttp session with nice user-agent default header.
    async with aiohttp.ClientSession(connector=_g.ahConnector,
                                     headers=_g.httpHeaders) as ahSession:
        # ahSession only exists in this context manager block, so to avoid
        # having to pass it 1 million times through subroutines, we bind it
        # to a global variable first
        _g.ahSession = ahSession
        # Start the REPL
        pmt = prompt.peepPrompt()
        pmtloop = await pmt.loop()

    # Program shutdown code.
    # Backup 
    backup.createBackup()
    # Stop autosave
    t_autosave.cancel()
    # prompt_toolkit bug if you spam commands like crazy
    count = 0
    for t in asyncio.all_tasks():
        if "wait_for_timeout()" in repr(t):
            count += 1
            t.cancel()
    _debug(f"{count} timeout tasks cancelled.")
    print("Exiting... zzzpeep")


if __name__ == "__main__":
    main()
