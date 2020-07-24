"""
peepdoi.py
----------

Functions which take DOIs as input and return something.
"""

import asyncio
from unicodedata import normalize

import aiohttp

from ._shared import *


def to_article(doi):
    """
    Blocking version of to_article_cr(). Useful as an external API as then
    the user need not worry about using asyncio.

    Returns the article dictionary if the DOI lookup succeeds. Otherwise raises
    ValueError.
    """
    article = asyncio.run(to_article_cr(doi))
    if article["title"] is None:
        raise ValueError(f"Invalid DOI '{doi}' given.")
    else:
        return article


async def to_article_cr(doi, client_session=None):
    """
    Uses Crossref API to obtain article metadata using a DOI. Returns a
    dictionary that is immediately suitable for use in _g.articleList.

    Incorrect journal short forms are corrected here. The dictionary containing
    the corrections is stored in _g.

    This can optionally be be passed an aiohttp.HTTPSession instance together
    with the actual DOI. If not, then a new HTTPSession is generated.
    """
    crossref_url = f"https://api.crossref.org/works/{doi}"

    # Instantiate a new ClientSession if none was provided. However, we do need
    # to remember whether the ClientSession was provided: if it wasn't, then
    # we should close it at the end.
    if client_session is None:
        session = aiohttp.ClientSession()
    else:
        session = client_session

    try:
        # Fetch the data from CrossRef
        async with session.get(crossref_url) as resp:
            d = await resp.json()
    except aiohttp.client_exceptions.ContentTypeError:
        # Lookup failed. But we can't just pass _ret.FAILURE, because we need
        # to know which doi caused the error. So we pass None in every other
        # field. It's a bit overkill, but it seems more consistent than
        # choosing one arbitrarily, and less hassle than returning a tuple.
        a = {"doi": doi, "title": None, "authors": None, "year": None,
             "journalLong": None, "journalShort": None, "volume": None,
             "issue": None, "pages": None}
    else:
        d = d["message"]    # avoid repeating this subscript many times
        a = {}
        a["doi"] = doi
        # Minor hack to convert 'J.R.J.' to 'J. R. J.'.
        # The alternative involves re.split(), I think that's overkill.
        a["authors"] = [{"family": normalize("NFKC", auth["family"]),
                         "given": normalize("NFKC", auth["given"].replace(". ", ".").replace(".",". ").rstrip())}
                        for auth in d["author"]]
        a["year"] = int(d["published-print"]["date-parts"][0][0]) \
            if "published-print" in d \
            else int(d["published-online"]["date-parts"][0][0])
        a["journalLong"] = d["container-title"][0]

        ###  Abstract -- unfortunately many of the DOIs don't have abstracts on
        ###  Crossref. Also we'd need to strip HTML tags. But in principle this
        ###  does work.
        # if "abstract" in d:
        #     a["abstract"] = d["abstract"]

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

        # Process title
        a["title"] = d["title"][0]
        # Convert Greek letters in ACS titles to their Unicode equivalents
        for i in _g.greek2Unicode.keys():
            if f".{i}." in a["title"]:
                a["title"] = a["title"].replace(f".{i}.", _g.greek2Unicode[i])

        try:
            a["volume"] = int(d["volume"])
        except KeyError:   # no volume
            a["volume"] = ""
        except ValueError:  # it's a range (!!!)
            a["volume"] = d["volume"]
        try:
            a["issue"] = int(d["issue"])
        except KeyError:   # no issue
            a["issue"] = ""
        except ValueError:  # it's a range (!!!)
            a["issue"] = d["issue"]
        a["pages"] = d["page"] if "page" in d else ""
    finally:
        # If the ClientSession instance wasn't provided, close it.
        if client_session is None:
            await session.close()
        return a


def to_fname(doi, type):
    """
    Converts a given doi to a filename. The filename is absolute and is
    constructed using _g.currentPath.
    """
