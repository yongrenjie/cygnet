"""
This module contains helper functions which act on PDFs or DOIs.
"""

import subprocess
from pathlib import Path

from crossref.restful import Works

from constants import _g, _exitCode, _error, _debug


def openDOIType(doi, format, p):
    """Opens a DOI as an article PDF, SI PDF, or web page."""

    # Get the link to the pdf / website
    if format == 'p':
        fname = p.parent / "pdf" / "{}.pdf".format(doi).replace("/","#")
        fname = fname.resolve()
        if not fname.exists():
            return _error("ref {} (p): file {} not found".format(refno, fname))
    elif format == 's':
        fname = p.parent / "si" / "{}.pdf".format(doi).replace("/","#")
        fname = fname.resolve()
        if not fname.exists():
            return _error("ref {} (s): file {} not found".format(refno, fname))
    elif format == 'w':
        fname = "https://doi.org/{}".format(doi)
    else:
        raise RuntimeError("AGH!!! _openDOIType() got an argument it shouldn't have!")

    # Open the thing, error out if it can't be found
    try:
        subprocess.run(["open", fname], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        return _error("ref {}: file {} could not be opened".format(refno, fname))
    else:
        ec = _exitCode.SUCCESS
    return ec


def parseRefNo(s):
    """
    Takes a string s and returns a list of int reference numbers.
    Returns None if any error is found.
     e.g. "1"      -> [1]
          "1-5"    -> [1, 2, 3, 4, 5]
          "1-4,43" -> [1, 2, 3, 4, 43]
    """
    s = s.split(",")
    t = []
    try:
        for i in s:
            if "-" in i:
                min, max = i.split("-")   # ValueError if too many entries
                if min >= max:
                    raise ValueError("you silly billy")
                for m in range(int(min), int(max) + 1):
                    t.append(m)
            else:
                t.append(int(i))          # ValueError if not castable to int
    except ValueError:
        return None
    else:
        return t
