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
from . import backup
from . import commands
from ._shared import *


def main():
    """
    Entry point for the program. Perform startup tasks, then run the
    main coroutine.
    """
    # Resize terminal
    cols, rows = os.get_terminal_size()
    cols = max(cols, 175)
    rows = max(rows, 50)
    sys.stdout.write(f"\x1b[8;{rows};{cols}t")

    # Parse sys.argv
    parser = argparse.ArgumentParser()
    parser.add_argument("db",
                        help=("Folder to load upon startup. "
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

    # Read in the folder specified in argv.
    infile = Path(args.db).resolve().expanduser()
    if (infile / "db.yaml").is_file():
        # This automatically performs a backup.
        commands.read(infile / "db.yaml")

    # Run main coroutine until complete
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main_coro())
    loop.close()


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
