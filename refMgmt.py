"""
This module contains helper functions which act on PDFs or DOIs.
"""

import re
import subprocess
from pathlib import Path
from copy import deepcopy

from crossref.restful import Works
from unidecode import unidecode

import listFmt
from _shared import _g, _ret, _error, _debug


def parseRefnoFormat(args, abbrevs=None):
    """
    Parses a list of reference numbers + formats from the prompt.
    Does some preprocessing then delegates to parseRefno and parseFormat.
    Useful for commands o(pen) and c(ite).
    """
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


def parseRefno(s):
    """
    Takes a string s and returns a list of int reference numbers.
    Returns None if any error is found.
     e.g. "1"      -> [1]
          "1-5"    -> [1, 2, 3, 4, 5]
          "1-4,43" -> [1, 2, 3, 4, 43]
    """
    s = s.split(",")
    t = set()
    try:
        for i in s:
            if i == "":
                continue
            if "-" in i:
                min, max = i.split("-")   # ValueError if too many entries
                min = int(min)
                max = int(max)
                if min >= max:
                    return _ret.FAILURE
                for m in range(min, max + 1):
                    t.add(m)
            else:
                t.add(int(i))          # ValueError if not castable to int
    except (ValueError, TypeError):
        # ValueError -- something couldn't be casted to int
        # TypeError  -- input wasn't iterable
        return _ret.FAILURE
    else:
        return t


def parseFormat(s):
    """
    Takes a string s and returns a list of [A-Za-z] characters inside.
    If there aren't any such characters, this returns an empty list, not None.
    """
    t = []
    try:
        for i in s:
            if i.isalpha():
                t.append(i)
    except (AttributeError, TypeError):
        # AttributeError -- isalpha() failed (e.g. integers)
        # TypeError      -- input wasn't iterable
        return _ret.FAILURE
    else:
        return t


def unicode2Latex(s):
    """
    Replaces Unicode characters in a string with their LaTeX equivalents.
    """
    for char in _g.unicodeLatexDict:
        s = s.replace(char, _g.unicodeLatexDict[char])
    return s


def openDOIType(doi, refno, fmt, p):
    """
    Opens a DOI as an article PDF, SI PDF, or web page.
    """

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
        return _error("openDOIType: incorrect fmt {} received".format(fmt))

    # Open the thing, error out if it can't be found
    try:
        subprocess.run(["open", fname], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        return _error("openDOIType: ref {}: file {} could not be opened".format(refno, fname))
    else:
        return _ret.SUCCESS


def makeCitation(article, fmt):
    """
    Takes an article dictionary and returns it in a suitable plaintext format.

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
        a["pages"] = a["pages"].replace('-','\u2013')   # en dash for page number
        if "issue" in a:
            return "*{}* **{}**, *{}* ({}), {}. [DOI: {}](https://doi.org/{}).".format(
                a["journalShort"], a["year"], a["volume"],
                a["issue"], a["pages"], a["doi"], a["doi"]
            )
        else:
            return "*{}* **{}**, *{},* {}. [DOI: {}](https://doi.org/{}).".format(
                a["journalShort"], a["year"], a["volume"],
                a["pages"], a["doi"], a["doi"]
            )
    elif fmt == 'M':
        authorString = "; ".join((listFmt.fmtAuthor(auth, "acs") for auth in a["authors"]))
        if "issue" in a:
            return "{} {}. *{}* **{}**, *{}* ({}), {}. [DOI: {}](https://doi.org/{}).".format(
                authorString, a["title"], a["journalShort"], a["year"], a["volume"],
                a["issue"], a["pages"], a["doi"], a["doi"]
            )
        else:
            return "{} {}. *{}* **{}**, *{},* {}. [DOI: {}](https://doi.org/{}).".format(
                authorString, a["title"], a["journalShort"], a["year"], a["volume"],
                a["pages"], a["doi"], a["doi"]
            )

    # BibLaTeX
    elif fmt == 'b':
        refName = unidecode(a["authors"][0]["family"]) + \
            str(a["year"]) + \
            "".join(c for c in "".join(w for w in a["journalShort"].split())
                    if c.isupper())
        authNames = " and ".join(unicode2Latex(listFmt.fmtAuthor(auth, style="bib"))
                                 for auth in a["authors"])
        s = "@article{{{},\n".format(refName) + \
            "    doi = {{{}}},\n".format(a["doi"]) + \
            "    author = {{{}}},\n".format(authNames) + \
            "    journal = {{{}}},\n".format(a["journalShort"]).replace(". ", ".\\ ") + \
            "    title = {{{}}},\n".format(unicode2Latex(a["title"])) + \
            "    year = {{{}}},\n".format(a["year"]) + \
            ("    volume = {{{}}},\n".format(a["volume"]) if "volume" in a else "") + \
            ("    issue = {{{}}},\n".format(a["issue"]) if "issue" in a else "") + \
            ("    pages = {{{}}},\n".format(a["pages"]) if "pages" in a else "").replace("-","--") + \
            "}"
        return s
    else:
        return _error("makeCitation: incorrect fmt {} received".format(fmt))


def getMetadataFromDOI(doi):
    """
    Uses Crossref API to obtain article metadata using a DOI. Returns a
    dictionary that is immediately suitable for use in _g.articleList.

    Incorrect journal short forms are corrected here. The dictionary containing
    the corrections is stored in _g.
    """
    # TODO: can't print text before the doi is fetched.
    # Maybe we can turn this into a coroutine anyway, with a spinner. :-)
    print("getMetadataFromDOI: fetching data for {} from Crossref...".format(doi))
    d = _g.works.doi(doi)
    if d is None:   # lookup failed
        return _ret.FAILURE
    else:
        a = {}
        a["doi"] = doi
        a["authors"] = [{"family": auth["family"], "given": auth["given"]}
                        for auth in d["author"]]
        a["year"] = int(d["published-print"]["date-parts"][0][0]) \
            if "published-print" in d else int(d["published-online"]["date-parts"][0][0])
        a["journalLong"] = d["container-title"][0]
        a["journalShort"] = d["short-container-title"][0] \
            if "short-container-title" in d else a["journalLong"]
        if a["journalShort"] in _g.journalReplacements:
            a["journalShort"] = _g.journalReplacements[a["journalShort"]]
        a["title"] = d["title"][0]
        a["volume"] = int(d["volume"]) if "volume" in d else ""
        a["issue"] = int(d["issue"]) if "issue" in d else ""
        a["pages"] = d["page"] if "page" in d else ""
        return a


def diffArticles(aold, anew):
    """
    Compare metadata of two articles. To be used when (e.g.) calling updateRef(),
    so that the user can either accept or reject the changes.

    The proposed change is aold -> anew, i.e. aold is being replaced with anew.

    This function returns the number of keys for which the two dictionaries'
    values differ. But it also prints coloured output showing what data is going
    to be removed / added. It's designed to be similar to git diff, except that
    a more nuanced shade of red is used (to avoid confusion with errors), and a
    more turquoise shade of green is used (to avoid confusion with the prompt).
    """
    if aold == anew:
        return 0
    else:
        ao = deepcopy(aold)
        an = deepcopy(anew)
        ndiff = 0
        # Fix the author key. Everything else can just be autoconverted into
        #  strings.
        if "authors" in ao:
            ao["authors"] = ", ".join(listFmt.fmtAuthor(auth) for auth in ao["authors"])
        if "authors" in an:
            an["authors"] = ", ".join(listFmt.fmtAuthor(auth) for auth in an["authors"])
        # Get the set of all items in ao and an
        # Don't compare the timeAdded and timeOpened fields
        allKeys = sorted((set(ao) | set(an)) - {"timeAdded", "timeOpened"})
        # Get field width
        maxlen = max(len(key) for key in allKeys)
        # Check individual keys
        for key in allKeys:
            # Key is in both. We expect this to be the case most of the time.
            if key in ao and key in an:
                if ao[key] == an[key]:
                    print("{:>{}}: {}".format(key, maxlen, ao[key]))
                else:
                    ndiff += 1
                    print("{:>{}}: {}- {}{}".format(key, maxlen, _g.ansiDiffRed,
                                                    ao[key], _g.ansiReset))
                    print("{:>{}}  {}+ {}{}".format("", maxlen, _g.ansiDiffGreen,
                                                    an[key], _g.ansiReset))
            # Key is in ao only, i.e. it is being removed.
            elif key in ao and key not in an:
                ndiff += 1
                print("{:>{}}: {}- {}{}".format(key, maxlen, _g.ansiDiffRed,
                                                ao[key], _g.ansiReset))
            # Key is in an only, i.e. it is being added.
            elif key not in ao and key in an:
                ndiff += 1
                print("{:>{}}: {}+ {}{}".format(key, maxlen, _g.ansiDiffGreen,
                                                an[key], _g.ansiReset))
        return ndiff


def getDOIFromPDF(p):
    """
    Attempts to get a DOI from a PDF.

    This method is *very* crude. It just utilises strings(1) and some magic regexes.
    """
    pass

