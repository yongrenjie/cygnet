"""
This module contains helper functions which act on PDFs or DOIs.
"""

import subprocess
from pathlib import Path
from copy import deepcopy

from crossref.restful import Works
from unidecode import unidecode

from constants import _g, _exitCode, _error, _debug
import listFmt


def parseRefnoFormat(args, abbrevs=None):
    """Parses a list of reference numbers + formats from the prompt.
    Does some preprocessing then delegates to parseRefno and parseFormat.
    Useful for commands o(pen) and c(ite)."""
    # Preprocess args
    argstr = ",".join(args)
    # Replace long forms with short forms, e.g. pdf -> p for openRef()
    if abbrevs is not None:
        for shortForm, longForm in abbrevs.items():
            argstr = argstr.replace(longForm, shortForm)
    # Find the first character in argstr that isn't [0-9,-]
    x = next((i for i, c in enumerate(argstr) if c not in "1234567890,-"), len(argstr))
    # Then repackage them
    argRefno = argstr[:x]
    argFormat = argstr[x:]

    return (parseRefno(argRefno), parseFormat(argFormat))


def openDOIType(doi, refno, fmt, p):
    """Opens a DOI as an article PDF, SI PDF, or web page."""

    # Get the link to the pdf / website
    if fmt == 'p':
        fname = p.parent / "pdf" / "{}.pdf".format(doi).replace("/","#")
        fname = fname.resolve()
        if not fname.exists():
            return _error("openDOIType: ref {} (p): file {} not found".format(refno, fname))
    elif fmt == 's':
        fname = p.parent / "si" / "{}.pdf".format(doi).replace("/","#")
        fname = fname.resolve()
        if not fname.exists():
            return _error("openDOIType: ref {} (s): file {} not found".format(refno, fname))
    elif fmt == 'w':
        fname = "https://doi.org/{}".format(doi)
    else:
        # should never reach here because openRef has argument checking
        raise ValueError("openDOIType: incorrect fmt {} received".format(fmt))

    # Open the thing, error out if it can't be found
    try:
        subprocess.run(["open", fname], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        return _error("openDOIType: ref {}: file {} could not be opened".format(refno, fname))
    else:
        ec = _exitCode.SUCCESS
    return ec


def parseRefno(s):
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
            if i == "":
                continue
            if "-" in i:
                min, max = i.split("-")   # ValueError if too many entries
                if min >= max:
                    raise ValueError("you silly billy")
                for m in range(int(min), int(max) + 1):
                    t.append(m)
            else:
                t.append(int(i))          # ValueError if not castable to int
    except (ValueError, TypeError):
        # ValueError -- something couldn't be casted to int
        # TypeError  -- input wasn't iterable
        return None
    else:
        return t


def parseFormat(s):
    """
    Takes a string s and returns a list of [A-Za-z] characters inside.
    If there aren't any such characters, this returns an empty list, not None.
    If the input is invalid (e.g. it's not iterable, or a list of ints), then
     it returns None.
    """
    t = []
    try:
        for i in s:
            if i.isalpha():
                t.append(i)
    except (AttributeError, TypeError):
        # AttributeError -- isalpha() failed (e.g. integers)
        # TypeError      -- input wasn't iterable
        return None
    else:
        return t


def makeCitation(article, fmt):
    """Takes an article dictionary and returns it in a suitable plaintext format.

    Formats allowed (so far):
     - 'b': BibLaTeX.
     - 'd': DOI only.
     - 'm': Short Markdown. Only has journal, year, volume, issue, pages, DOI.
     - 'M": Long Markdown. Includes author names and title as well.
    """
    a = deepcopy(article)
    if fmt == 'd':
        return a["doi"]

    # Markdown short & long
    elif fmt == 'm':
        a["page"] = a["page"].replace('-','\u2013')   # en dash for page number
        if "issue" in a:
            return "*{}* **{}**, *{}* ({}), {}. [DOI: {}](https://doi.org/{}).".format(
                a["journal_short"], a["year"], a["volume"],
                a["issue"], a["page"], a["doi"], a["doi"]
            )
        else:
            return "*{}* **{}**, *{},* {}. [DOI: {}](https://doi.org/{}).".format(
                a["journal_short"], a["year"], a["volume"],
                a["page"], a["doi"], a["doi"]
            )
    elif fmt == 'M':
        authorString = "; ".join((listFmt.fmtAuthor(auth, "acs") for auth in a["authors"]))
        if "issue" in a:
            return "{} {}. *{}* **{}**, *{}* ({}), {}. [DOI: {}](https://doi.org/{}).".format(
                authorString, a["title"], a["journal_short"], a["year"], a["volume"],
                a["issue"], a["page"], a["doi"], a["doi"]
            )
        else:
            return "{} {}. *{}* **{}**, *{},* {}. [DOI: {}](https://doi.org/{}).".format(
                authorString, a["title"], a["journal_short"], a["year"], a["volume"],
                a["page"], a["doi"], a["doi"]
            )

    # BibLaTeX
    elif fmt == 'b':
        refName = unidecode(a["authors"][0]["family"]) + \
            str(a["year"]) + \
            "".join(c for c in "".join(w for w in a["journal_long"].split()
                                       if w.lower() not in ["a", "an", "the"])
                    if c.isupper())
        authNames = " and ".join(unicode2Latex(listFmt.fmtAuthor(auth, style="bib"))
                                 for auth in a["authors"])
        s = "@article{{{},\n".format(refName) + \
                       "    doi = {{{}}},\n".format(a["doi"]) + \
                       "    author = {{{}}},\n".format(authNames) + \
                       "    journal = {{{}}},\n".format(a["journal_short"]) + \
                       "    title = {{{}}},\n".format(a["title"]) + \
                       "    year = {{{}}},\n".format(a["year"]) + \
                      ("    volume = {{{}}},\n".format(a["volume"]) if "volume" in a else "") + \
                      ("    issue = {{{}}},\n".format(a["issue"]) if "issue" in a else "") + \
                      ("    pages = {{{}}},\n".format(a["pages"]) if "pages" in a else "") + \
                       "}"
        return s
    else:
        raise ValueError("makeCitation: incorrect fmt {} received".format(fmt))


def unicode2Latex(s):
    """Replaces Unicode characters in a string with their LaTeX equivalents."""
    for char in _g.unicodeLatexDict:
        s = s.replace(char, _g.unicodeLatexDict[char])
    return s
