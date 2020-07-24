"""
backup.py
---------

Autosave and backup functions which try to make sure that changes are not lost.
"""

import asyncio
import filecmp
from pathlib import Path
from datetime import datetime
from operator import attrgetter

from . import commands
from ._shared import *


async def autosave():
    """
    Checks every interval seconds for changes. If changes have been made, saves
    _g.articleList to _g.currentPath.
    """
    interval = 2
    while True:
        try:
            await asyncio.sleep(interval)
            # Right now we only have one article list at a time, and
            #  changes just contains sentinel values.
            l = len(_g.changes)
            if _g.articleList and _g.currentPath and l != 0:
                _debug(f"autosave: found {l} change{_p(l)}: "
                       f"{' '.join(_g.changes)}")
                commands.write(silent=True)
                _debug("autosave complete")
                _g.changes = []
        except asyncio.CancelledError:
            break


def createBackup():
    """
    Saves _g.articleList to the backups folder if it's different from the
    previous backup.
    """
    maxBackups = 5

    if maxBackups == 0:
        return
    if _g.articleList != [] and _g.currentPath is not None:
        dbName = _g.currentPath.name
        # Figure out the folder name
        backupFolder = _g.currentPath.parent / "backups"
        if not backupFolder.exists():
            backupFolder.mkdir()
        # Create the backup file
        now = datetime.now().strftime(".%y%m%d_%H%M%S")
        fname = backupFolder / (dbName + now)
        commands.write(fname, silent=True)
        _debug("created backup file")

        # Create list of all backup files; most recent is last
        backups = sorted([p for p in backupFolder.iterdir()],
                         key=attrgetter('name'))
        # Check if the new backup is identical to the previous one. If so, we
        # delete the newest one instead of the oldest one.
        if filecmp.cmp(backups[-1], backups[-2]):
            # They are the same, delete the newest one
            backups[-1].unlink()
            backups.pop(-1)
            _debug("new backup is same, deleting it")
        # Otherwise, delete the oldest backup(s) until there are only maxBackups
        # backup files.
        while len(backups) > maxBackups:
            _debug(f"deleting old backup {backups[0]}")
            backups[0].unlink()
            backups.pop(0)
