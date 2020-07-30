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
from . import fileio
from ._shared import *


async def autosave():
    """
    Checks every interval seconds for changes. If changes have been made, saves
    _g.articleList to _g.currentPath.
    """
    interval = 2
    try:
        while True:
            await asyncio.sleep(interval)
            l = len(_g.changes)
            if len(_g.articleList) != 0 and l != 0:
                _debug(f"autosave: found {l} change{_p(l)}: "
                       f"{' '.join(_g.changes)}")
                fileio.write_articles(_g.articleList, _g.currentPath / "db.yaml")
                _debug("autosave complete")
                _g.changes = []
    except asyncio.CancelledError:
        # If the program is quit, save one last time before exiting
        if len(_g.articleList) != 0:
            fileio.write_articles(_g.articleList, _g.currentPath / "db.yaml")
            _debug("exit save complete, exiting autosave task")


def create_backup():
    """
    Saves _g.articleList to the backups folder if it's different from the
    previous backup.
    """
    max_backups = 5

    if max_backups == 0:
        return
    if _g.articleList != [] and _g.currentPath is not None:
        dbName = _g.currentPath.name
        # Figure out the folder name
        backup_folder = _g.currentPath / "backups"
        if not backup_folder.exists():
            backup_folder.mkdir()
        # Create the backup file
        now = datetime.now().strftime(".%y%m%d_%H%M%S")
        backup_fname = backup_folder / (dbName + now)
        fileio.write_articles(_g.articleList, backup_fname)
        _debug("created backup file")

        # Create list of all backup files; most recent is last
        backups = sorted([p for p in backup_folder.iterdir()],
                         key=attrgetter('name'))
        # Check if the new backup is identical to the previous one. If so, we
        # delete the newest one instead of the oldest one.
        if len(backups) >= 2 and filecmp.cmp(backups[-1], backups[-2]):
            # They are the same, delete the newest one
            backups[-1].unlink()
            backups.pop(-1)
            _debug("new backup is same, deleting it")
        # Otherwise, delete the oldest backup(s) until there are only
        # max_backups backup files.
        while len(backups) > max_backups:
            _debug(f"deleting old backup {backups[0]}")
            backups[0].unlink()
            backups.pop(0)
