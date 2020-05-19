"""
This module stores all the global variables (state variables) as well
as some useful constants.

It also contains trivial functions that are used repeatedly throughout the code.
"""

import sys
import subprocess
from enum import Enum
from pathlib import Path
from functools import wraps

from time import time
from crossref.restful import Etiquette


class _g():
    # Storage of global variables.
    version_number = "0.1"
    my_etiquette = Etiquette('PeepLaTeX',
                             version_number,
                             'https://github.com/yongrenjie',
                             'yongrenjie@gmail.com')
    # List of dictionaries, each containing a single article.
    articleList = []
    # pathlib.Path object pointing to the current database.
    currentPath = None
    # Number of changes made to articleList that haven't been autosaved.
    changes = 0
    # Debugging mode on/off
    debug = True
    # Maximum number of backups to keep
    maxBackups = 5
    # Time interval for autosave (seconds)
    autosaveInterval = 10
    # Colours for the prompt
    # Check for Dark Mode (OS X)
    darkmode = True
    if sys.platform == "darwin":
        try:
            subprocess.run(["defaults", "read", "-g", "AppleInterfaceStyle"],
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, check=True)
        except subprocess.CalledProcessError:
            darkmode = False
    ptPink = "#f589d1" if darkmode else "#8629ab"
    ptGreen = "#17cf48" if darkmode else "#2a731f"
    ansiRed = "\033[38;5;196m"
    ansiGrey = "\033[38;5;240m" if darkmode else"\033[38;5;246m"
    ansiReset = "\033[0m"


class _exitCode(Enum):
    SUCCESS = 0
    FAILURE = 1
    pass


def timedeco(fn):
    """
    Decorator which prints time elapsed for a function call.
    """
    @wraps(fn)
    def timer(*args, **kwargs):
        now = time()
        rval = fn(*args, **kwargs)
        _debug("{}: time elapsed: {:.3f} ms".format(fn.__name__,
                                                   (time() - now) * 1000))
        return rval
    return timer


def _error(msg):
    """
    Generic error printer.
    """
    print("{}error:{} {}{}{}".format(_g.ansiRed, _g.ansiReset,
                                     _g.ansiGrey, msg, _g.ansiReset))
    return _exitCode.FAILURE


def _debug(msg):
    if _g.debug is True:
        print("{}{}{}".format(_g.ansiGrey, msg, _g.ansiReset))

