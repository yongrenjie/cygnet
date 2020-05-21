"""
This module stores all the global variables (state variables) as well
as some useful constants.

It also contains trivial functions that are used repeatedly throughout the code.
"""

import sys
import subprocess
import asyncio
from locale import getpreferredencoding as gpe
from enum import Enum
from pathlib import Path
from functools import wraps
from time import time

from crossref.restful import Works, Etiquette


class _g():
    # Storage of global variables.
    version_number = "0.1"
    myEtiquette = Etiquette('PeepLaTeX',
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
    # Time interval for autosave (seconds). Note that this doesn't actually
    #  save unless changes have been made, i.e. changes > 0.
    autosaveInterval = 1
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

    # Colours for various stuff. Names should be self-explanatory.
    ptPink = "#f589d1" if darkmode else "#8629ab"
    ptGreen = "#17cf48" if darkmode else "#2a731f"
    ptBlue = "#45c6ed" if darkmode else "#3344de"
    ansiErrorRed = "\033[38;5;196m"
    ansiErrorText = "\033[38;5;210m" if darkmode else "\033[38;5;88m"
    ansiDiffRed = "\033[38;5;202m" if darkmode else "\033[38;5;124m"
    ansiDiffGreen = "\033[38;5;50m" if darkmode else "\033[38;5;30m"
    ansiDebugGrey = "\033[38;5;240m" if darkmode else "\033[38;5;246m"
    ansiReset = "\033[0m"
    # System preferred encoding. Probably UTF-8.
    gpe = gpe()
    # Crossref object.
    works = Works(etiquette=myEtiquette)

    unicodeLatexDict = {
        '\u00c0': '{\\`A}', '\u00c1': "{\\'A}", '\u00c2': '{\\^A}', '\u00c3': '{\\~A}',
        '\u00c4': '{\\"A}', '\u00c5': '{\\AA}', '\u00c6': '{\\AE}', '\u00c7': '{\\cC}',
        '\u00c8': '{\\`E}', '\u00c9': "{\\'E}", '\u00ca': '{\\^E}', '\u00cb': '{\\"E}',
        '\u00cc': '{\\`I}', '\u00cd': "{\\'I}", '\u00ce': '{\\^I}', '\u00cf': '{\\"I}',
        '\u00d0': '{\\DH}', '\u00d1': '{\\~N}', '\u00d2': '{\\`O}', '\u00d3': "{\\'O}",
        '\u00d4': '{\\^O}', '\u00d5': '{\\~O}', '\u00d6': '{\\"O}', '\u00d7': '\\(\\times\\)',
        '\u00d8': '{\\O}',  '\u00d9': '{\\`U}', '\u00da': "{\\'U}", '\u00db': '{\\^U}',
        '\u00dc': '{\\"U}', '\u00dd': "{\\'Y}", '\u00de': '{\\TH}', '\u00df': '{\\ss}',

        '\u00e0': '{\\`a}',  '\u00e1': "{\\'a}",  '\u00e2': '{\\^a}',  '\u00e3': '{\\~a}',
        '\u00e4': '{\\"a}',  '\u00e5': '{\\aa}',  '\u00e6': '{\\ae}',  '\u00e7': '{\\cc}',
        '\u00e8': '{\\`e}',  '\u00e9': "{\\'e}",  '\u00ea': '{\\^e}',  '\u00eb': '{\\"e}',
        '\u00ec': '{\\`\i}', '\u00ed': "{\\'\i}", '\u00ee': '{\\^\i}', '\u00ef': '{\\"\i}',
        '\u00f0': '{\\dh}',  '\u00f1': '{\\~n}',  '\u00f2': '{\\`o}',  '\u00f3': "{\\'o}",
        '\u00f4': '{\\^o}',  '\u00f5': '{\\~o}',  '\u00f6': '{\\"o}',  '\u00f7': '\\(\\div\\)',
        '\u00f8': '{\\o}',   '\u00f9': '{\\`u}',  '\u00fa': "{\\'u}",  '\u00fb': '{\\^u}',
        '\u00fc': '{\\"u}',  '\u00fd': "{\\'y}",  '\u00fe': '{\\th}',  '\u00ff': '{\\"y}',

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

    # Dictionary containing correct (as listed in CASSI) abbreviations of some journals.
    journalReplacements = {
        "Proceedings of the National Academy of Sciences": "Proc. Acad. Natl. Sci. U. S. A.",
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
        }

    # Dictionary containing short forms for common terms in journal names, which can be
    #  used when printing lists of articles (to save space). OK this is a bit small, but
    #  in principle we can expand this in future.
    jNameAbbrevs = {
        "Nucl Magn Reson": "NMR",
    }


class _exitCode(Enum):
    SUCCESS = 0
    FAILURE = 1
    pass


def _timedeco(fn):
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


def _asynctimedeco(fn):
    """
    Decorator which prints time elapsed for an async function to run to completion.

    Note that using this decorator effectively makes the function block until it has
     finished, i.e. it makes it no longer actually async!!
    It's only useful for profiling timings
    """
    @wraps(fn)
    async def timer(*args, **kwargs):
        now = time()
        rval = await fn(*args, **kwargs)
        _debug("{}: time elapsed: {:.3f} ms".format(fn.__name__,
                                                   (time() - now) * 1000))
        return rval
    return timer


def _error(msg):
    """
    Generic error printer.
    """
    print("{}error:{} {}{}{}".format(_g.ansiErrorRed, _g.ansiReset,
                                     _g.ansiErrorText, msg, _g.ansiReset))
    return _exitCode.FAILURE


def _debug(msg):
    if _g.debug is True:
        print("{}{}{}".format(_g.ansiDebugGrey, msg, _g.ansiReset))


def _p(n, singular='', plural='s'):
    """Tells us whether to use plural or singular."""
    try:  # if n is some iterable
        n = len(n)
    except TypeError:
        pass
    return singular if n == 1 else plural


async def _copy(s):
    """Copy s to the clipboard.

    Doesn't pretend to be cross-platform. Only for macOS.
    Linux (specifically WSL) support to be added in future.
    """
    # pbcopy(1) and pbpaste(1) for macOS
    if sys.platform == "darwin":
        proc = await asyncio.create_subprocess_exec("pbcopy",
                                                    stdin=asyncio.subprocess.PIPE)
        await proc.communicate(input=s.encode(gpe()))
        return
    else:
        return _error("_copy: unsupported OS, not copied to clipboard")
