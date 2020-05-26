"""
This module contains helper functions which act on PDFs or DOIs.
"""

import re
import sys
import subprocess
import asyncio
from pathlib import Path
from copy import deepcopy

import aiohttp
from unidecode import unidecode

import listFmt
from _shared import (_g, _ret, _error, _debug, _progress, _spinner)


def parseRefnoFormat(args, abbrevs=None):
    """
    Parses a list of reference numbers + formats from the prompt.
    Does some preprocessing then delegates to parseRefno and parseFormat.
    Useful for commands o(pen) and c(ite).
    """
    # Check for 'all' -- this makes our job substantially easier because
    # 'all' is the refno and everything else is the format
    if args[0] == "all":
        argRefno = "all"
        argFormat = ",".join(args[1:])
    # Otherwise we have to do it the proper way
    else:
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
    # The easy way out
    if s == ["all"]:
        return list(range(1, len(_g.articleList) + 1))
    # Otherwise we've got to parse it.
    t = set()   # to avoid duplicates
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
        return list(t)


def parseFormat(s):
    """
    Takes a string s and returns a list of [A-Za-z] characters inside.
    If there aren't any such characters, this returns an empty list, not None.
    """
    t = set()
    try:
        for i in s:
            if i.isalpha():
                t.add(i)
    except (AttributeError, TypeError):
        # AttributeError -- isalpha() failed (e.g. integers)
        # TypeError      -- input wasn't iterable
        return _ret.FAILURE
    else:
        return list(t)


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


async def getMetadataFromDOI(doi, session):
    """
    Uses Crossref API to obtain article metadata using a DOI. Returns a
    dictionary that is immediately suitable for use in _g.articleList.

    Incorrect journal short forms are corrected here. The dictionary containing
    the corrections is stored in _g.

    This needs to be passed an aiohttp.HTTPSession instance together with the
    actual DOI.
    """
    url = "https://api.crossref.org/works/{}".format(doi)

    try:
        async with session.get(url) as resp:
            d = await resp.json()
    except aiohttp.client_exceptions.ContentTypeError:   # lookup failed
        # Lookup failed. But we can't just pass _ret.FAILURE, because we need
        # to know which doi caused the error. So we pass None in every other
        # field. It's a bit overkill, but it seems more consistent than
        # choosing one arbitrarily, and less hassle than returning a tuple.
        return {"doi": doi, "title": None, "authors": None, "year": None,
                "journalLong": None, "journalShort": None, "volume": None,
                "issue": None, "pages": None}
    else:
        d = d["message"]    # avoid repeating this subscript many times
        a = {}
        a["doi"] = doi
        a["authors"] = [{"family": auth["family"], "given": auth["given"]}
                        for auth in d["author"]]
        a["year"] = int(d["published-print"]["date-parts"][0][0]) \
            if "published-print" in d else int(d["published-online"]["date-parts"][0][0])
        a["journalLong"] = d["container-title"][0]

        # Short journal title.
        if "short-container-title" in d:
            try:
                a["journalShort"] = d["short-container-title"][0]
            except IndexError:
                # 10.1126/science.280.5362.421, for example, has an empty list
                # in d["short-container-title"]...
                a["journalShort"] = a["journalLong"]
        else:
            a["journalShort"] = a["journalLong"]
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


def PDFToDOI(p):
    """
    Attempts to get a DOI from a PDF.

    This method is *very* crude. It just utilises strings(1) and some magic regexes.
    """
    pass


async def getPDFURLFromDOI(doi, session):
    """
    Scrapes HTTP headers and responses for information as to which publisher
    is responsible for the data, and then constructs the URL to the full PDF.

    In principle extensible to SI, but not yet. (It may actually be sufficiently
    complicated to warrant its own function.)

    Arguments:
        doi (str): The DOI.
        session  : The aiohttp.ClientSession() instance.
    """
    doi_url = "https://doi.org/{}".format(doi)
    publisher = None

    # not much point making these global
    class _PublisherFound(Exception):
        pass
    # First item is the regex to match against.
    # Second item is the string to check the matched group for.
    publisherRegex = {
        'wiley': [re.compile(r"""<meta name=["']citation_publisher["']\s+content=["'](.+?)["']\s*/?>"""), "John Wiley"],
        'elsevier': [re.compile(r"""<input type="hidden" name="redirectURL" value="https%3A%2F%2Fwww.sciencedirect.com%2Fscience%2Farticle%2Fpii%2F(.+?)%3Fvia%253Dihub" id="redirectURL"/>"""), ""],
        'tandf': [re.compile(r"""<meta name=["']dc.Publisher["']\s+content=["'](.+?)["']\s*/?>"""), "Taylor"],
        'annrev': [re.compile(r"""<meta name=["']dc.Publisher["']\s+content=["'](.+?)["']\s*/?>"""), "Annual Reviews"],
    }
    publisherFmtStrings = {
        "acs": "https://pubs.acs.org/doi/pdf/{}",
        "wiley": "https://onlinelibrary.wiley.com/doi/pdf/{}",
        "elsevier": "https://www.sciencedirect.com/science/article/pii/{}/pdfft",
        "nature": "https://www.nature.com/articles/{}.pdf",
        "science": "https://science.sciencemag.org/content/sci/{}.full.pdf",
        "springer": "https://link.springer.com/content/pdf/{}.pdf",
        "tandf": "https://www.tandfonline.com/doi/pdf/{}",
        "annrev": "https://www.annualreviews.org/doi/pdf/{}",
    }

    try:
        async with session.get(doi_url) as resp:
            if resp.status != 200:
                return _error("getPDFURLFromDOI: URL '{}' returned "
                              "{} ({})".format(psrc, resp.status, resp.reason))
            # Shortcut for ACS, don't need to read content
            if "Set-Cookie" in resp.headers and "pubs.acs.org" in resp.headers["Set-Cookie"]:
                publisher = "acs"
                identifier = doi
                raise _PublisherFound
            # Shortcut for Nature, don't need to read content
            if "X-Forwarded-Host" in resp.headers and "www.nature.com" in resp.headers["X-Forwarded-Host"]:
                publisher = "nature"
                identifier = doi.split('/', maxsplit=1)[1]
                raise _PublisherFound
            # Shortcut for Science, don't need to read content.
            # Note that this doesn't work for Sci Advances
            if "Link" in resp.headers and "science.sciencemag.org" in resp.headers["Link"]:
                publisher = "science"
                identifier = resp.headers["Link"].split(">")[0].split("/content/")[1]
                raise _PublisherFound
            # Shortcut for Springer
            if "Set-Cookie" in resp.headers and ".springer.com" in resp.headers["Set-Cookie"]:
                publisher = "springer"
                identifier = doi
                raise _PublisherFound
            # Shortcut for Taylor and Francis
            if "Set-Cookie" in resp.headers and ".tandfonline.com" in resp.headers["Set-Cookie"]:
                publisher = "tandf"
                identifier = doi
                raise _PublisherFound

            # Otherwise, start reading the content
            e = resp.get_encoding()
            async for line in resp.content:
                line = line.decode(e)  # it's read as bytes
                # Search the line for every regex
                for pname, regexKeyword in publisherRegex.items():
                    match = regexKeyword[0].search(line)
                    if match and regexKeyword[1] in match.group(1):
                        publisher = pname
                        if publisher in ["acs", "wiley", "tandf", "annrev"]:
                            identifier = doi
                        elif publisher in ["elsevier"]:
                            identifier = match.group(1)
                        raise _PublisherFound
    except (aiohttp.client_exceptions.ContentTypeError,
            aiohttp.client_exceptions.InvalidURL,
            aiohttp.client_exceptions.ClientConnectorError):
        return (doi, _error("getPDFURLFromDOI: URL '{}' "
                            "not accessible".format(url_doi)))
    except _PublisherFound:
        return (doi, publisherFmtStrings[publisher].format(identifier))
    else:
        return (doi, _error("getPDFURLFromDOI: could not find full text for doi {}".format(doi)))


async def savePDF(path, doi, fmt):
    """
    Saves a PDF into the database itself.

    path should be a string. It can either be a Web page, or a path to a file.
    doi is the DOI.
    fmt is either 'pdf' or 'si'.
    """

    # first, boot out any silly ideas
    if '/' not in path:
        return _error("savePDF: invalid path '{}'".format(path))

    # This is crude, but should work as long as we only use absolute paths.
    type = "file" if path.startswith('/') else "url"

    # Construct the destination path (where the PDF should be saved to).
    pdest = _g.currentPath.parent / fmt / (doi.replace('/','#') + ".pdf")

    if type == "file":
        # Process and check source path. Note that dragging-and-dropping
        # into the terminal gives us escaped spaces, hence the replace().
        psrc = Path(path.replace("\ "," ").strip())
        if not psrc.is_file():
            return _error("savePDF: file {} not found".format(psrc))
        else:
            try:
                proc = subprocess.run(["cp", str(psrc), str(pdest)],
                                      check=True)
            except subprocess.CalledProcessError:
                return _error("savePDF: file {} could not be copied"
                              "to {}".format(psrc, pdest))
            else:
                return _ret.SUCCESS

    if type == "url":
        psrc = path.strip()
        try:
            async with _g.ahSession.get(psrc) as resp:
                # Handle bad HTTP status codes.
                if resp.status != 200:
                    return _error("savePDF: URL '{}' returned "
                                  "{} ({})".format(psrc, resp.status,
                                                   resp.reason))
                # Check if content-type is really a PDF.
                if "application/pdf" not in resp.content_type:
                    return _error("savePDF: URL '{}' returned content-type "
                                  "'{}'".format(psrc, resp.content_type))
                # OK, so by now we are pretty sure we have a working link to a
                # PDF. Try to get the file size.
                filesize = None
                try:
                    filesize = int(resp.headers["content-length"])
                except (KeyError, ValueError):
                    pass
                # Create spinner.
                if filesize is not None:
                    prog = _progress(filesize/(2**20), fstr="{:.2f}")  # in MB
                    spin = asyncio.create_task(_spinner("Downloading file", prog, "MB"))
                else:
                    spin = asyncio.create_task(_spinner("Downloading file"))

                # Stream the content.
                with open(pdest, 'wb') as fp:
                    chunkSize = 2048   # bytes
                    while True:  # good argument for assignment expression here
                        chunk = await resp.content.read(chunkSize)
                        if not chunk:
                            break
                        fp.write(chunk)
                        if filesize is not None:
                            prog.incr(chunkSize/(2**20))
                # Cancel spinner
                spin.cancel()
                await asyncio.sleep(0)

        # lookup failed
        except (aiohttp.client_exceptions.ContentTypeError,
                aiohttp.client_exceptions.InvalidURL,
                aiohttp.client_exceptions.ClientConnectorError):
            return _error("savePDF: URL '{}' not accessible".format(psrc))
        else:
            return _ret.SUCCESS


