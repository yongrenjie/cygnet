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
        return _error("openDOIType: incorrect format {} received".format(fmt))

    # Open the thing, error out if it can't be found
    try:
        subprocess.run(["open", fname], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        return _error("openDOIType: ref {}: file {} could not be opened".format(refno, fname))
    else:
        return _ret.SUCCESS


async def savePDF(path, doi, fmt):
    """
    Saves a PDF into the database itself.

    path should be a string. It can either be a Web page, or a path to a file.
    doi is the DOI.
    fmt is either 'pdf' or 'si'.
    """

    # first, boot out any silly ideas
    if '/' not in str(path):
        return _error("savePDF: invalid path '{}'".format(path))

    # This is crude, but should work as long as we only use absolute paths.
    type = "file" if str(path).startswith('/') else "url"

    # Construct the destination path (where the PDF should be saved to).
    pdest = _g.currentPath.parent / fmt / (doi.replace('/','#') + ".pdf")
    # mkdir -p the folder if it doesn't already exist.
    if not pdest.parent.exists():
        pdest.parent.mkdir(parents=True)

    if type == "file":
        # Process and check source path. Note that dragging-and-dropping
        # into the terminal gives us escaped spaces, hence the replace().
        psrc = str(path).replace("\\ "," ").strip()
        for escapedChar, char in _g.pathEscapes:
            psrc = psrc.replace(escapedChar, char)
        psrc = Path(psrc)
        if not psrc.is_file():
            return _error("savePDF: file {} not found".format(psrc))
        else:
            try:
                proc = subprocess.run(["cp", str(psrc), str(pdest)],
                                      check=True)
            except subprocess.CalledProcessError:
                return _error("savePDF: file {} could not be copied "
                              "to {}".format(psrc, pdest))
            else:
                return _ret.SUCCESS

    if type == "url":
        psrc = str(path).strip()
        try:
            async with _g.ahSession.get(psrc) as resp:
                # Handle bad HTTP status codes.
                if resp.status != 200:
                    return _error("savePDF: URL '{}' returned "
                                  "{} ({})".format(psrc, resp.status,
                                                   resp.reason))
                # Check if Elsevier is trying to redirect us.
                if "sciencedirect" in psrc and resp.content_type == "text/html":
                    # e = resp.get_encoding()
                    redirectRegex = re.compile(r"""window.location\s*=\s*'(https?://.+)';""")
                    text = await resp.text()
                    for line in text.split("\n"):
                        match = redirectRegex.search(line)
                        if match:
                            newurl = match.group(1)
                            _debug("Redirected by Elsevier, trying to fetch PDF from new URL")
                            newSave = asyncio.create_task(savePDF(newurl, doi, fmt))
                            await asyncio.wait([newSave])
                            return newSave.result()
                elif "wiley" in psrc and resp.content_type == "text/html":
                    text = await resp.text()
                    for line in text.split("\n"):
                        print(line)
                    return _error("screw wiley")
                # Otherwise, check if we are actually getting a PDF
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
        # strings.
        if "authors" in ao:
            ao.authors = ", ".join(ao.format_authors())
        if "authors" in an:
            an.authors = ", ".join(an.format_authors())
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


def PDFToDOI(path):
    """
    Attempts to extract a DOI from a PDF.

    This method is fairly crude. It just utilises strings(1) and some magic regexes.
    """
    raw_regexes = [
        r"""<prism:doi>(10.\d{4,9}/[-._;()/:a-zA-Z0-9]+)</prism:doi>""",
        r"""["'](?:doi|DOI):(10.\d{4,9}/[-._;()/:a-zA-Z0-9]+)["']""",
        r"""URI\s*\(https?://doi.org/(10.\d{4,9}/[-._;()/:a-zA-Z0-9]+)\)\s*>""",
        r"""URI\s*\((?:https?://)?www.nature.com/doifinder/(10.\d{4,9}/[-._;()/:a-zA-Z0-9]+)\)\s*>""",
        # This one works for some ACIE papers, but is too risky. It matches
        # against DOIs of cited papers too. Better to use WPS-ARTICLEDOI.
        # r"""/URI\(https?://(?:dx)?.doi.org/(10.\d{4,9}/[-._;()/:a-zA-Z0-9]+)\)""",
        r"""/WPS-ARTICLEDOI\s*\((10.\d{4,9}/[-._;()/:a-zA-Z0-9]+)\)""",
        r"""\((?:doi|DOI):\s*(10.\d{4,9}/[-._;()/:a-zA-Z0-9]+)\)""",
        r"""<rdf:li.+>(?:doi|DOI):(10.\d{4,9}/[-._;()/:a-zA-Z0-9]+)</rdf:li>""",
    ]
    regexes = [re.compile(regex) for regex in raw_regexes]
    class _DOIFound(Exception):
        pass

    p = Path(path)
    if not (p.exists() or p.is_file()):
        return _error("PDFToDOI: invalid path '{}' given".format(p))

    strings = subprocess.Popen(["strings", p], stdout=subprocess.PIPE)
    grep = subprocess.Popen(["grep", "-i", "doi"], stdin=strings.stdout, stdout=subprocess.PIPE)
    try:
        for line in grep.stdout:
            line = line.decode(_g.gpe).strip()
            for regex in regexes:
                match = regex.search(line)
                if match:
                    raise _DOIFound(match.group(1))
    except _DOIFound as e:
        doi = e.args[0]
        # Prune away any extra parentheses at the end.
        nopen = doi.count('(')
        nclose = doi.count(')')
        if nopen != nclose:
            doi = doi.rsplit(')', maxsplit=(nclose - nopen))[0]
        # Report success.
        return doi
    else:
        return _error("PDFToDOI: could not detect doi from PDF '{}'".format(p))


async def DOIToFullPDFURL(doi, session):
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
        'rsc': [re.compile(r"""<meta content=["']https://pubs.rsc.org/en/content/articlepdf/(.+?)["']\s+name="citation_pdf_url"\s*/>"""), ""],
    }
    publisherFmtStrings = {
        "acs": "https://pubs.acs.org/doi/pdf/{}",
        "wiley": "https://onlinelibrary.wiley.com/doi/pdfdirect/{}",
        "elsevier": "https://www.sciencedirect.com/science/article/pii/{}/pdfft",
        "nature": "https://www.nature.com/articles/{}.pdf",
        "science": "https://science.sciencemag.org/content/sci/{}.full.pdf",
        "springer": "https://link.springer.com/content/pdf/{}.pdf",
        "tandf": "https://www.tandfonline.com/doi/pdf/{}",
        "annrev": "https://www.annualreviews.org/doi/pdf/{}",
        "rsc": "https://pubs.rsc.org/en/content/articlepdf/{}",
    }

    try:
        async with session.get(doi_url) as resp:
            if resp.status != 200:
                return _error("DOIToFullPDFURL: URL '{}' returned "
                              "{} ({})".format(psrc, resp.status, resp.reason))
            # Shortcut for ACS, don't need to read content
            if any("pubs.acs.org" in h for h in resp.headers.getall("Set-Cookie", [])):
                publisher = "acs"
                identifier = doi
                raise _PublisherFound
            # Shortcut for Nature, don't need to read content
            elif any("www.nature.com" in h for h in resp.headers.getall("X-Forwarded-Host", [])):
                publisher = "nature"
                identifier = doi.split('/', maxsplit=1)[1]
                raise _PublisherFound
            # Shortcut for Science, don't need to read content.
            # Note that this doesn't work for Sci Advances
            elif any("science.sciencemag.org" in h for h in resp.headers.getall("Link", [])):
                publisher = "science"
                identifier = resp.headers["Link"].split(">")[0].split("/content/")[1]
                raise _PublisherFound
            # Shortcut for Springer
            elif any(".springer.com" in h for h in resp.headers.getall("Set-Cookie", [])):
                publisher = "springer"
                identifier = doi
                raise _PublisherFound
            # Shortcut for Taylor and Francis
            elif any(".tandfonline.com" in h for h in resp.headers.getall("Set-Cookie", [])):
                publisher = "tandf"
                identifier = doi
                raise _PublisherFound
            # Otherwise, start reading the content
            else:
                e = resp.get_encoding()
                async for line in resp.content:
                    line = line.decode(e)  # it's read as bytes
                    # Search the line for every regex
                    for pname, regexKeyword in publisherRegex.items():
                        match = regexKeyword[0].search(line)
                        if match and regexKeyword[1] in match.group(1):
                            publisher = pname
                            if publisher in ["wiley", "tandf", "annrev"]:
                                identifier = doi
                            elif publisher in ["elsevier"]:
                                identifier = match.group(1)
                            elif publisher in ["rsc"]:
                                identifier = match.group(1)
                            raise _PublisherFound
    except (aiohttp.client_exceptions.ContentTypeError,
            aiohttp.client_exceptions.InvalidURL,
            aiohttp.client_exceptions.ClientConnectorError):
        return (doi, _error("DOIToFullPDFURL: URL '{}' "
                            "not accessible".format(url_doi)))
    except _PublisherFound:
        return (doi, publisherFmtStrings[publisher].format(identifier))
    else:
        return (doi, _error("DOIToFullPDFURL: could not find full text for doi {}".format(doi)))

