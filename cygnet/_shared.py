__all__ = ["_g", "_sort", "_ret",
           "_helpdeco", "_timedeco",
           "_error", "_debug", "_p",
           "_copy", "_saveHist", "_clearHist", "_undo",
           ]
"""
This module stores all the global variables (state variables) as well
as some useful constants.

It also contains trivial functions that are used repeatedly throughout the code.
"""

import os
import sys
import subprocess
import asyncio
from locale import getpreferredencoding
from enum import Enum
from pathlib import Path
from functools import wraps
from time import time
from copy import deepcopy
from operator import itemgetter, attrgetter
from collections import deque

import aiohttp

from ._version import __version__


class _g():
    ### Global variables used to store the state of the programme.
    # List of dictionaries, each containing a single article.
    articleList = []
    # pathlib.Path object pointing to the current database.
    currentPath = None
    # pathlib.Path object pointing to the previous path, allowing 'cd -'.
    previousPath = None
    # Changes made to articleList that haven't been autosaved.
    changes = []

    # History which allows undo.
    maxHistory = 5
    articleListHistory = deque(maxlen=maxHistory)
    cmdHistory = deque(maxlen=maxHistory)

    # Default headers to use
    httpHeaders = {"user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.61 Safari/537.36",
                   "mailto": "yongrenjie@gmail.com",
                   }
    # aiohttp maximum concurrent requests & objects
    ahMaxRequests = 20
    ahConnector = aiohttp.TCPConnector(limit=ahMaxRequests)
    ahSession = None   # this is set in main()

    # Debugging mode on/off. This is set by argv
    debug = None

    # Check for Dark Mode (OS X)
    darkmode = True
    if sys.platform == "darwin":
        try:
            subprocess.run(["defaults", "read", "-g", "AppleInterfaceStyle"],
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL,
                           check=True)
        except subprocess.CalledProcessError:
            darkmode = False
    # Check for JupyterLab terminal
    if "JUPYTER_SERVER_ROOT" in os.environ:
        darkmode = False
    # Colours for various stuff. Names should be self-explanatory.
    a = lambda col: f"\033[38;5;{col}m"
    ptPurple  = "#e4b3ff" if darkmode else "#940172"
    ptPink    = "#f589d1" if darkmode else "#8629ab"
    ptGreen   = "#17cf48" if darkmode else "#2a731f"
    ptBlue    = "#45c6ed" if darkmode else "#3344de"
    ptRed     = "#f53d50" if darkmode else "#b00718"
    ansiErrorRed    = a(196)
    ansiErrorText   = a(210) if darkmode else a(88)
    ansiDiffRed     = a(203) if darkmode else a(125)
    ansiDiffGreen   = a(50)  if darkmode else a(28)
    ansiDebugGrey   = a(240) if darkmode else a(246)
    ansiHelpYellow  = a(220) if darkmode else a(88)
    ansiTitleBlue   = a(81)  if darkmode else a(19)
    ansiBold = "\033[1m"
    ansiReset = "\033[0m"

    # System preferred encoding. Probably UTF-8.
    gpe = getpreferredencoding()

    # Conversion of Unicode characters to LaTeX equivalents.
    unicodeLatexDict = {
        '\u00c0': '{\\`A}', '\u00c1': "{\\'A}", '\u00c2': '{\\^A}', '\u00c3': '{\\~A}',
        '\u00c4': '{\\"A}', '\u00c5': '{\\AA}', '\u00c6': '{\\AE}', '\u00c7': '{\\cC}',
        '\u00c8': '{\\`E}', '\u00c9': "{\\'E}", '\u00ca': '{\\^E}', '\u00cb': '{\\"E}',
        '\u00cc': '{\\`I}', '\u00cd': "{\\'I}", '\u00ce': '{\\^I}', '\u00cf': '{\\"I}',
        '\u00d0': '{\\DH}', '\u00d1': '{\\~N}', '\u00d2': '{\\`O}', '\u00d3': "{\\'O}",
        '\u00d4': '{\\^O}', '\u00d5': '{\\~O}', '\u00d6': '{\\"O}', '\u00d7': '\\(\\times\\)',
        '\u00d8': '{\\O}',  '\u00d9': '{\\`U}', '\u00da': "{\\'U}", '\u00db': '{\\^U}',
        '\u00dc': '{\\"U}', '\u00dd': "{\\'Y}", '\u00de': '{\\TH}', '\u00df': '{\\ss}',

        '\u00e0': '{\\`a}', '\u00e1': "{\\'a}", '\u00e2': '{\\^a}', '\u00e3': '{\\~a}',
        '\u00e4': '{\\"a}', '\u00e5': '{\\aa}', '\u00e6': '{\\ae}', '\u00e7': '{\\cc}',
        '\u00e8': '{\\`e}', '\u00e9': "{\\'e}", '\u00ea': '{\\^e}', '\u00eb': '{\\"e}',
        '\u00ec': '{\\`i}', '\u00ed': "{\\'i}", '\u00ee': '{\\^i}', '\u00ef': '{\\"i}',
        '\u00f0': '{\\dh}', '\u00f1': '{\\~n}', '\u00f2': '{\\`o}', '\u00f3': "{\\'o}",
        '\u00f4': '{\\^o}', '\u00f5': '{\\~o}', '\u00f6': '{\\"o}', '\u00f7': '\\(\\div\\)',
        '\u00f8': '{\\o}',  '\u00f9': '{\\`u}', '\u00fa': "{\\'u}", '\u00fb': '{\\^u}',
        '\u00fc': '{\\"u}', '\u00fd': "{\\'y}", '\u00fe': '{\\th}', '\u00ff': '{\\"y}',

        # Stray characters which I've needed but aren't systematically handled
        # https://www.johndcook.com/unicode_latex.html is really useful
        '\u0106': "{\\'C}",
        '\u0107': "{\\'c}",
        '\u010d': '{\\v{c}}',
        '\u0112': '{\\=E}',
        '\u0141': '{\\L{}}',
        '\u0142': '{\\l{}}',
        '\u0143': "{\\'N}",
        '\u0144': "{\\'n}",
        '\u2010': '-',
        '\u2013': '--',
        '\u2014': '---',
    }

    # Convert Greek letters to Unicode.
    greek2Unicode = {
        "Alpha": "\u0391", "Beta": "\u0392", "Gamma": "\u0393", "Delta": "\u0394",
        "Epsilon": "\u0395", "Zeta": "\u0396", "Eta": "\u0397", "Theta": "\u0398",
        "Iota": "\u0399", "Kappa": "\u039A", "Lamda": "\u039B", "Mu": "\u039C",
        "Nu": "\u039D", "Xi": "\u039E", "Omicron": "\u039F", "Pi": "\u03A0",
        "Rho": "\u03A1", "Sigma": "\u03A3", "Tau": "\u03A4", "Upsilon": "\u03A5",
        "Phi": "\u03A6", "Chi": "\u03A7", "Psi": "\u03A8", "Omega": "\u03A9",
        "alpha": "\u03B1", "beta": "\u03B2", "gamma": "\u03B3", "delta": "\u03B4",
        "epsilon": "\u03B5", "zeta": "\u03B6", "eta": "\u03B7", "theta": "\u03B8",
        "iota": "\u03B9", "kappa": "\u03BA", "lamda": "\u03BB", "mu": "\u03BC",
        "nu": "\u03BD", "xi": "\u03BE", "omicron": "\u03BF", "pi": "\u03C0",
        "rho": "\u03C1", "sigma": "\u03C3", "tau": "\u03C4", "upsilon": "\u03C5",
        "phi": "\u03C6", "chi": "\u03C7", "psi": "\u03C8", "omega": "\u03C9",
    }

    # Dictionary containing correct (as listed in CASSI) abbreviations of some journals.
    journalReplacements = {
        "Proceedings of the National Academy of Sciences": "Proc. Natl. Acad. Sci. U. S. A.",
        "The Journal of Chemical Physics": "J. Chem. Phys.",
        "Journal of Magnetic Resonance": "J. Magn. Reson.",
        "Journal of Magnetic Resonance (1969)": "J. Magn. Reson.",
        "Progress in Nuclear Magnetic Resonance Spectroscopy": "Prog. Nucl. Magn. Reson. Spectrosc.",
        "Magn Reson Chem": "Magn. Reson. Chem.",
        "Chemical Physics Letters": "Chem. Phys. Lett.",
        "Biochemistry Journal": "Biochem. J.",
        "Journal of Magnetic Resonance, Series A": "J. Magn. Reson., Ser. A",
        "Journal of Magnetic Resonance, Series B": "J. Magn. Reson., Ser. B",
        "J Biomol NMR": "J. Biomol. NMR",
        "Annual Reports on NMR Spectroscopy": "Annu. Rep. NMR Spectrosc.",
        "Angewandte Chemie International Edition": "Angew. Chem. Int. Ed.",
        "Nat Commun": "Nat. Commun.",
        }

    # Dictionary of escaped characters in paths.
    pathEscapes = {
        "\\ ": " ", "\\,": ",", "\\'": "'", '\\"': '"',
    }


class _sort():
    """
    Class that handles sorting of the article list.
    """
    # Class attributes that determine the default way of sorting
    mode = "time_added"
    reverse = False  # Oldest to newest

    @classmethod
    def sort(cls, mode=None, reverse=None, set_mode=True):
        """
        Sorts _g.articleList in-place using the mode and reverse parameters.
        If set_mode is True, additionally updates the class attributes, which
        represent the currently active mode.
        """
        # Read in the class attributes if sorting method is not specified
        if mode is None:
            mode = cls.mode
        if reverse is None:
            reverse = cls.reverse
        # Sort
        if mode == "year":
            # Year alone isn't enough to distinguish: so we use a combination
            # of year, then journal title, then first author surname
            _g.articleList.sort(key=lambda a: (a.year,
                                               a.journal_long,
                                               a.authors[0]["family"]),
                                     reverse=reverse)
        elif mode in ["time_opened", "time_added"]:
            _g.articleList.sort(key=attrgetter(mode), reverse=reverse)
        else:
            raise ValueError(f"invalid sort mode '{mode}' given")
        # Update the class attributes if necessary
        if set_mode:
            cls.mode, cls.reverse = mode, reverse


class _ret(Enum):
    SUCCESS = 0
    FAILURE = 1
    pass


def _helpdeco(fn):
    """
    Decorator which makes the function or coroutine take a parameter 'help'. If
    True, then the function prints its docstring and exits immediately.
    """
    # For ordinary functions
    @wraps(fn)
    def helpful(*args, help=False, **kwargs):
        if help:
            print(f"{_g.ansiHelpYellow}{fn.__doc__}{_g.ansiReset}")
            return _ret.SUCCESS
        else:
            return fn(*args, **kwargs)
    # For coroutines
    @wraps(fn)
    async def helpful_crt(*args, help=False, **kwargs):
        if help:
            print(f"{_g.ansiHelpYellow}{fn.__doc__}{_g.ansiReset}")
            return _ret.SUCCESS
        else:
            return await fn(*args, **kwargs)
    # Return the appropriate one
    if asyncio.iscoroutinefunction(fn):
        return helpful_crt
    else:
        return helpful


def _timedeco(fn):
    """
    Decorator which prints time elapsed for a function call.

    This isn't used anymore (was mainly used for development), but we keep it
    here just in case.
    """
    @wraps(fn)
    def timedFn(*args, **kwargs):
        now = time()
        rval = fn(*args, **kwargs)
        _debug("{}: time elapsed: {:.3f} ms".format(fn.__name__,
                                                   (time() - now) * 1000))
        return rval
    return timedFn


def _error(msg):
    """
    Generic error printer.
    """
    print(f"{_g.ansiErrorRed}error:{_g.ansiReset} "
          f"{_g.ansiErrorText}{msg}{_g.ansiReset}")
    return _ret.FAILURE


def _debug(msg):
    if _g.debug is True:
        print("{}{}{}".format(_g.ansiDebugGrey, msg, _g.ansiReset))


def _p(n, singular='', plural='s'):
    """
    Tells us whether to use plural or singular.
    """
    try:  # if n is some iterable
        n = len(n)
    except TypeError:
        pass
    return singular if n == 1 else plural


async def _copy(s):
    """
    Copy s to the clipboard.

    Doesn't pretend to be cross-platform. Only for macOS.
    Linux (specifically WSL) support to be added in future.
    """
    # pbcopy(1) and pbpaste(1) for macOS
    if sys.platform == "darwin":
        proc = await asyncio.create_subprocess_exec("pbcopy",
                                                    stdin=asyncio.subprocess.PIPE)
        await proc.communicate(input=s.encode(_g.gpe))
        return _ret.SUCCESS
    else:
        return _error("_copy: unsupported OS, not copied to clipboard")


def _saveHist(cmd, args):
    """
    Saves the articleList just before applying the command cmd.
    """
    cmd = cmd + " " + " ".join(args)
    if _g.debug is True:
        _debug("saving history before command {}".format(cmd))
    _g.cmdHistory.append(cmd)
    _g.articleListHistory.append(deepcopy(_g.articleList))


def _clearHist():
    """
    Wipes the history. To be done just before loading a new file.
    If we don't do that, weesa may be in big doo doo.
    """
    _g.cmdHistory.clear()
    _g.articleListHistory.clear()


@_helpdeco
def _undo():
    """
    Tries to rewind history.
    """
    try:
        _g.articleList = _g.articleListHistory.pop()
        _g.changes += ["undo"]
        print("undid command: {}".format(_g.cmdHistory.pop()))
    except IndexError:
        return _error("undo: no more history")
    else:
        return _ret.SUCCESS
