"""
This module contains helper functions which act on PDFs or DOIs.
"""


import re
import sys
import subprocess
import asyncio
from unicodedata import normalize
from pathlib import Path
from copy import deepcopy

import aiohttp
from unidecode import unidecode

from ._shared import *


def unicode2Latex(s):
    """
    Replaces Unicode characters in a string with their LaTeX equivalents.
    """
    for char in _g.unicodeLatexDict:
        s = s.replace(char, _g.unicodeLatexDict[char])
    return s
