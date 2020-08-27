"""
peepcls.py
----------

Contains the Article, DOI, and Spinner classes.
"""

import re
import sys
import subprocess
import asyncio
import urllib
import shutil
from pathlib import Path
from unicodedata import normalize
from operator import attrgetter
from itertools import cycle

import aiohttp
from unidecode import unidecode

from ._shared import *


class Article():
    def __init__(self, title=None, authors=None,
                 journal_long=None, journal_short=None,
                 year=None, volume=None, issue=None,
                 pages=None, doi=None,
                 time_added=None, time_opened=None):
        self.title = title
        self.authors = authors
        self.journal_long = journal_long
        self.journal_short = journal_short
        self.year = year
        self.volume = volume
        self.issue = issue
        self.pages = pages
        self.doi = doi
        self.time_added = time_added
        self.time_opened = time_opened

    def __eq__(self, other):
        if not isinstance(other, Article):
            return NotImplemented
        # Compare attributes one by one, except for time_added and time_opened
        return (self.title == other.title
                and self.authors == other.authors
                and self.journal_long == other.journal_long
                and self.journal_short == other.journal_short
                and self.journal_short == other.journal_short
                and self.year == other.year
                and self.volume == other.volume
                and self.issue == other.issue
                and self.pages == other.pages
                and self.doi == other.doi)

    def format_authors(self, style):
        """
        Convert author names to a suitable format.

        Parameters
        ----------
        style : str
            Style in which the output should be produced. Must be one of
            "display", "acs", or "bib". The output is as follows:
                 - "display": "JRJ Yong"
                 - "acs"    : "Yong, J. R. J."
                 - "bib"    : "Yong, Jonathan R. J."
                 - "full"   : given + family concatenated

        Returns
        -------
        A list of appropriately formatted strings, one for each author, or None
        if self.authors is None.
        """
        def format_one_author(author, style):
            """
            Helper function that does it for one author.
            """
            # Check If there's no given name.
            # We should probably try to handle the no family name case, but
            # I'm not sure when we will actually come across an example...
            if "given" not in author or author["given"] == []:
                return author["family"]
            # Otherwise...
            family_name = author["family"]
            given_names = author["given"]
            if style == "display":
                return ("".join(n[0] for n in given_names.split())
                        + " " + author["family"])
            elif style == "acs":
                return (author["family"] + ", "
                        + ". ".join(n[0] for n in given_names.split()) + ".")
            elif style == "bib":
                s = author["family"] + ", " + author["given"]
                return s.replace(". ", ".\\ ")  # Must use control spaces
            elif style == "full":
                return author["given"] + " " + author["family"]
            # Otherwise, grumble.
            else:
                raise ValueError(f"Invalid value '{style}' for style.")

        if self.authors is not None:
            return [format_one_author(author, style) for author in self.authors]

    def format_short_journalname(self):
        """
        Extracts the short journal name from an article and tries to make it as
        short as possible, e.g. by removing periods as well as using some
        acronyms like "NMR".

        Returns
        -------
        A string with the shortest possible form.
        """
        abbrevs = {
            "Nucl Magn Reson": "NMR",
        }

        name = self.journal_short.replace(".", "")
        for long, short in abbrevs.items():
            name = name.replace(long, short)
        return name

    def get_volume_info(self):
        """
        Extracts volume number, issue number, and page numbers from an article
        and returns the string "vol (issue), page-page", or "vol, page-page" if
        no issue number is present.

        Returns
        -------
        The volume info as a string.
        """
        if self.issue:
            return f"{self.volume} ({self.issue}), {self.pages}"
        else:
            return f"{self.volume}, {self.pages}"

    def get_availability(self):
        """
        Checks whether the PDF and SI are available for a given article.

        Returns
        -------
        List of (bool, bool) corresponding to PDF and SI availability.
        """
        return [self.to_fname(type).is_file() for type in ("pdf", "si")]

    def get_availability_string(self):
        """
        Generates a string reflecting the presence or absence of a PDF or SI
        for a given article.

        Returns
        -------
        A string with a green tick / red cross for 'pdf' and 'si' formats.
        """
        exists = self.get_availability()
        symbols = ['\u2714' if e else '\u2718' for e in exists]
        colors = [_g.ansiDiffGreen if e else _g.ansiDiffRed for e in exists]
        return (f"{colors[0]}{symbols[0]}{_g.ansiReset}pdf  "
                f"{colors[1]}{symbols[1]}{_g.ansiReset}si")

    def to_fname(self, type):
        """
        Converts a given article to a filename or URL. Filenames are absolute,
        constructed using _g.currentPath.

        Parameters
        ----------
        type : str
            "pdf", "si", or "web". The abbreviations "p", "s", and "w" are
            allowed as well.

        Returns
        -------
        The filename as a pathlib.Path object, or URL as a string.
        """
        if type in ["pdf", "p"]:
            return _g.currentPath / "pdf" / f"{self.doi.replace('/','#')}.pdf"
        elif type in ["si", "s"]:
            return _g.currentPath / "si" / f"{self.doi.replace('/','#')}.pdf"
        elif type in ["web", "w"]:
            return f"https://doi.org/{self.doi}"
        else:
            raise ValueError("Invalid type '{type}' given")

    def to_citation(self, type):
        """
        Constructs a citation from the given article. Does not copy to the
        clipboard; that's the job of _copy().

        Arguments
        ---------
        type : str
            "bib", "markdown", "Markdown", "doi", or "word". The abbreviations
            "b", "m", "M", "d", and "w" are also allowed.

        Returns
        -------
        The citation as a string.
        """
        acs_authors = "; ".join(self.format_authors("acs"))
        pages_with_endash = self.pages.replace("-", "\u2013")
        # Actually, not using quote() generally gives results that work fine.
        # The only issue is that when using Markdown URLs with parentheses in
        # Jupyter notebooks, the conversion to HTML gets it wrong, thinking
        # that the URL ends at the first close parentheses in the URL. (In
        # the notebook itself, it is fine, only the conversion to HTML messes
        # up.) So we might as well escape them generally.
        doi_url = f"https://doi.org/{urllib.parse.quote(self.doi)}"

        # Just DOI
        if type in ["doi", "d"]:
            return self.doi

        # Markdown short
        elif type in ["markdown", "m"]:
            if self.issue:
                return (f"*{self.journal_short}* **{self.year}**, "
                        f"*{self.volume}* ({self.issue}), "
                        f"{pages_with_endash}. "
                        f"[DOI: {self.doi}]({doi_url}).")
            else:
                return (f"*{self.journal_short}* **{self.year}**, "
                        f"*{self.volume},* "
                        f"{pages_with_endash}. "
                        f"[DOI: {self.doi}]({doi_url}).")

        # Markdown long
        elif type in ["Markdown", "M"]:
            if self.issue:
                return (f"{acs_authors} {self.title}. "
                        f"*{self.journal_short}* **{self.year}**, "
                        f"*{self.volume}* ({self.issue}), "
                        f"{pages_with_endash}. "
                        f"[DOI: {self.doi}]({doi_url}).")
            else:
                return (f"{acs_authors} {self.title}. "
                        f"*{self.journal_short}* **{self.year}**, "
                        f"*{self.volume},* "
                        f"{pages_with_endash}. "
                        f"[DOI: {self.doi}]({doi_url}).")

        # Word
        elif type in ["word", "w"]:
            if self.issue:
                return (f"{acs_authors} "
                        f"{self.journal_short} {self.year}, "
                        f"{self.volume} ({self.issue}), "
                        f"{pages_with_endash}.")
            else:
                return (f"{acs_authors} "
                        f"{self.journal_short} {self.year}, "
                        f"{self.volume}, "
                        f"{pages_with_endash}.")

        # BibLaTeX
        elif type in ["bib", "b"]:
            # Create (hopefully) unique identifier
            author_decoded = unidecode(self.authors[0]["family"])
            journal_initials = "".join(c for c in self.journal_short
                                       if c.isupper())
            ref_identifier = f"{author_decoded}{self.year}{journal_initials}"
            # Author names in bib style
            author_names = " and ".join(self.format_authors("bib"))
            journal = self.journal_short.replace(". ", ".\\ ")
            # Open and close braces
            # Truthfully we don't need this. However, including the doubled
            # curly braces in the f-string makes vim's indentation go crazy.
            open, close = "{", "}"
            # Make the citation
            s = (f"@article{open}{ref_identifier},\n"
                 f"    doi = {{{self.doi}}},\n"
                 f"    author = {{{author_names}}},\n"
                 f"    journal = {{{journal}}},\n"
                 f"    title = {{{self.title}}},\n"
                 f"    year = {{{self.year}}},\n")
            if self.volume is not None:
                s += f"    volume = {{{self.volume}}},\n"
            if self.issue is not None:
                s += f"    issue = {{{self.issue}}},\n"
            if self.pages is not None:
                s += f"    pages = {{{self.pages.replace('-', '--')}}},\n"
            s += close
            # Replace Unicode characters with their LaTeX equivalents
            for char in _g.unicodeLatexDict:
                s = s.replace(char, _g.unicodeLatexDict[char])
            return s
        else:
            raise ValueError("Invalid citation type '{type}' given")

    def diff(self, other):
        """
        Compare metadata of two Articles. This prints to stdout the differences
        that would occur if self was replaced with other.

        Parameters
        ----------
        other : Article
            Another Article instance to compare with.

        Returns
        -------
        ndiffs : int
            The number of fields which the two Articles differ in.
        """
        if not isinstance(other, Article):
            raise TypeError("Can only diff two Articles.")

        ndiffs = 0
        # Check for equality first (don't need to print anything in this case)
        if self == other:  # defined via __eq__
            return 0

        # Compare all attributes except for time added and opened
        attribs = sorted(set(vars(self)) - {"time_added", "time_opened"})
        # Get field width (for pretty printing)
        maxlen = max(len(attrib) for attrib in attribs)
        # Check individual keys
        for attrib in attribs:
            # We need to convert authors to a string
            if attrib == "authors":
                if self.authors is not None:
                    old_value = ", ".join(self.format_authors("full"))
                else:
                    old_value = None
                if other.authors is not None:
                    new_value = ", ".join(other.format_authors("full"))
                else:
                    new_value = None
            # Other attributes can be accessed via the dict
            else:
                old_value = attrgetter(attrib)(self)
                new_value = attrgetter(attrib)(other)
            # Compare them
            if old_value is not None and old_value == new_value:
                print(f"{attrib:>{maxlen}}: {old_value}")
            else:
                ndiffs += 1
                if old_value is not None:
                    print(f"{attrib:>{maxlen}}: "
                          f"{_g.ansiDiffRed}- {old_value}{_g.ansiReset}")
                    attrib = ""  # avoid printing the attribute name twice
                if new_value is not None:
                    print(f"{attrib:>{maxlen}}: "
                          f"{_g.ansiDiffGreen}+ {new_value}{_g.ansiReset}")
        return ndiffs

    def to_newarticle(self):
        """
        Fetches a new set of metadata from Crossref. Returns a new Article
        instance.

        It's just a wrapper around the DOI method.
        """
        return DOI(self.doi).to_article(metadata=True)

    async def to_newarticle_cr(self, client_session=None):
        """
        Asynchronous version of fetch_metadata().
        """
        return await DOI(self.doi).to_article_cr(client_session=client_session)

    async def register_pdf(self, path, type, client_session=None):
        """
        Copies a PDF for an article into the database ('registering' it).

        Parameters
        ----------
        path : str or pathlib.Path
            Link to the file, or to a webpage.
        type : str from {"pdf", "si"}
            Indicates whether it's a PDF or SI.
        """
        # Figure out whether it's a file on disk, or a web page. This is crude,
        # but should work as long as we only use absolute paths.
        src_type = "file" if str(path).startswith('/') else "url"

        # Construct the destination path (where the PDF should be saved to).
        pdest = self.to_fname(type)
        # mkdir -p the folder if it doesn't already exist.
        if not pdest.parent.exists():
            pdest.parent.mkdir(parents=True)

        # Copy a file over.
        if src_type == "file":
            # Process and check source path. Note that dragging-and-dropping
            # into the terminal gives us escaped spaces, hence the replace().
            psrc = str(path).replace("\\ "," ").strip()
            for escapedChar, char in _g.pathEscapes:
                psrc = psrc.replace(escapedChar, char)
            psrc = Path(psrc)
            if not psrc.is_file():
                return _error("The specified PDF was not found.")
            else:
                shutil.copy2(psrc, pdest)

        # Downloading a file...
        if src_type == "url":
            # Instantiate a new ClientSession if none was provided. However, we
            # do need to remember whether the ClientSession was provided: if it
            # wasn't, then we should close it at the end.
            if client_session is None:
                # Make sure we have a polite header, though.
                session = aiohttp.ClientSession(headers=_g.httpHeaders)
            else:
                session = client_session

            psrc = str(path).strip()
            try:
                async with session.get(psrc) as resp:
                    # Check if Elsevier is trying to redirect us.
                    if ("sciencedirect" in psrc
                            and resp.content_type == "text/html"):
                        # Construct a regex which detects where it's
                        # redirecting us to, then scan the website text for the
                        # redirect URL.
                        redirectRegex = re.compile(
                            r"""window.location\s*=\s*'(https?://.+)';"""
                        )
                        text = await resp.text()
                        for line in text.split("\n"):
                            match = redirectRegex.search(line)
                            if match:
                                newurl = match.group(1)
                                _debug("Redirected by Elsevier")
                                # We just need to recursively call ourself with
                                # the new URL.
                                new_save = asyncio.create_task(
                                    self.register_pdf(newurl, type))
                                await asyncio.wait([new_save])
                                return new_save.result()
                    # Otherwise, check if we are actually getting a PDF
                    if "application/pdf" not in resp.content_type:
                        return _error(f"The URL '{psrc}' was not a PDF file.")

                    # OK, so by now we are pretty sure we have a working link
                    # to a PDF. Try to get the file size.
                    filesize = None
                    try:
                        filesize = int(resp.headers["content-length"])
                    except (KeyError, ValueError):
                        pass
                    # Create spinner.
                    total = filesize/(2 ** 20) if filesize else 0
                    async with Spinner((f"Downloading PDF for "
                                        f"'{self.title}'..."),
                                       total=total,
                                       units="MB", fstr="{:.2f}") as spinner:
                        # Stream the content directly into pdest
                        with open(pdest, "wb") as fp:
                            chunk_size = 2048   # bytes
                            while True:  # good argument for := here
                                chunk = await resp.content.read(chunk_size)
                                if not chunk:
                                    break
                                fp.write(chunk)
                                if filesize is not None:
                                    spinner.increment(chunk_size/(2**20))
            except aiohttp.client_exceptions.InvalidURL:
                return _error(f"Invalid URL {psrc} provided.")
            except aiohttp.ClientResponseError as e:
                return _error(f"HTTP status {e.status}: {e.message}")

            # Close off the ClientSession instance if it was only created for
            # this.
            if client_session is None:
                await session.close()

        return _ret.SUCCESS


class DOI():
    def __init__(self, doi):
        self.doi = doi

    async def to_article_cr(self, client_session=None):
        """
        Uses Crossref API to obtain article metadata using a DOI. Returns a
        dictionary that is immediately suitable for use in _g.articleList.

        Incorrect journal short forms are corrected here. The dictionary containing
        the corrections is stored in _g.

        This can optionally be be passed an aiohttp.HTTPSession instance together
        with the actual DOI. If not, then a new HTTPSession is generated.

        Note that this coroutine always fetches metadata (as opposed to the
        to_article() method which doesn't if the metadata keyword argument is
        set to False).

        Parameters
        ----------
        doi : str
            DOI to look up.
        client_session : aiohttp.HTTPSession
            aiohttp session instance to use.

        Returns
        -------
        Article instance. If the lookup was successful, all the Article fields
        will be populated. If not, then all fields will be None, except for the
        DOI field, which will contain the DOI that was looked up.
        """
        crossref_url = f"https://api.crossref.org/works/{self.doi}"

        # Instantiate a new ClientSession if none was provided. However, we do need
        # to remember whether the ClientSession was provided: if it wasn't, then
        # we should close it at the end.
        if client_session is None:
            # Make sure we have a polite header, though.
            session = aiohttp.ClientSession(headers=_g.httpHeaders)
        else:
            session = client_session

        try:
            article = Article(doi=self.doi)
            # Fetch the data from CrossRef
            async with session.get(crossref_url) as resp:
                d = await resp.json()
        except aiohttp.client_exceptions.ContentTypeError:
            # Lookup failed. But we can't just pass _ret.FAILURE, because we need
            # to know which doi caused the error. So we create a blank Article with
            # only the DOI field populated (everything else is by default set to
            # None in __init__()).
            pass
        else:
            d = d["message"]    # avoid repeating this subscript many times
            # Minor hack to convert 'J.R.J.' to 'J. R. J.'.
            # The alternative involves re.split(), I think that's overkill.
            article.authors = [{"family": normalize("NFKC", auth["family"]),
                                "given": normalize("NFKC", auth["given"].replace(". ", ".").replace(".",". ").rstrip())}
                               for auth in d["author"]]
            article.year = int(d["published-print"]["date-parts"][0][0]) \
                if "published-print" in d \
                else int(d["published-online"]["date-parts"][0][0])
            article.journal_long = d["container-title"][0]

            # Short journal title.
            if "short-container-title" in d:
                try:
                    article.journal_short = d["short-container-title"][0]
                except IndexError:
                    # 10.1126/science.280.5362.421, for example, has an empty list
                    # in d["short-container-title"]...
                    article.journal_short = article.journal_long
            else:
                article.journal_short = article.journal_long
            if article.journal_short in _g.journalReplacements:
                article.journal_short = _g.journalReplacements[article.journal_short]

            # Process title
            article.title = d["title"][0]
            # Convert Greek letters in ACS titles to their Unicode equivalents
            for i in _g.greek2Unicode.keys():
                if f".{i}." in article.title:
                    article.title = article.title.replace(f".{i}.", _g.greek2Unicode[i])

            # Volume
            try:
                article.volume = int(d["volume"])
            except KeyError:   # no volume
                pass
            except ValueError:  # it's a range (!!!)
                article.volume = d["volume"]
            # Issue
            try:
                article.issue = int(d["issue"])
            except KeyError:   # no issue
                pass
            except ValueError:  # it's a range (!!!)
                article.issue = d["issue"]
            # Pages
            try:
                article.pages = d["page"]
            except KeyError:
                pass
        finally:
            # If the ClientSession instance wasn't provided, close it.
            if client_session is None:
                await session.close()

        # We can't put the return inside the finally, because exceptions that occur
        # in the else block are only raised *after* the finally block. So, if the
        # return is placed inside finally, exceptions are never raised.
        return article

    def to_article(self, metadata=True):
        """
        Convert a DOI to an article. Useful as an external API as the user need
        not bother with managing asyncio coroutines.

        The `metadata` parameter can be set to False in order to not look up the
        metadata on CrossRef. In that case, an "empty" Article instance will be
        returned which only has the doi attribute populated.

        Note that this should not be called with metadata=True from within an
        existing coroutine. Instead, use:

            article = await DOI(doi).to_article_cr()

        Parameters
        ----------
        doi : str
            DOI to look up.
        get_metadata : bool, optional
            Whether to fetch metadata from Crossref.

        Returns
        -------
        Article instance, with metadata if requested.

        Raises
        ------
        ValueError
            If metadata was requested for an invalid DOI.
        """
        if not metadata:
            return Article(doi=self.doi)
        else:
            article = asyncio.run(self.to_article_cr())
            if article.title is None:
                raise ValueError(f"Invalid DOI '{self.doi}' given.")
            else:
                return article

    def to_citation(self, type):
        """
        Generates a citation from a DOI via an Article instance. Looks up
        information on Crossref along the way.

        Parameters
        ----------
        doi : str
            DOI to look up.
        type : str
            "bib", "markdown", "Markdown", "doi", or "word". The abbreviations
            "b", "m", "M", "d", and "w" are also allowed.

        Returns
        -------
        The citation as a string.
        """
        return self.to_article().to_citation(type)

    async def to_full_pdf_url(self, client_session=None):
        """
        Scrapes HTTP headers and responses for information as to which publisher
        is responsible for the data, and then constructs the URL to the full PDF.

        In principle extensible to SI, but not yet. (It may actually be sufficiently
        complicated to warrant its own function.)

        Parameters
        ----------
        client_session : aiohttp.ClientSession, optional
            The aiohttp.ClientSession instance to use.

        Returns
        -------
        The URL as as tring.
        """
        doi_url = "https://doi.org/{}".format(self.doi)
        publisher = None

        class _PublisherFound(Exception):
            pass
        # First item is the regex to match against.
        # Second item is the string to check the matched group for.
        publisherRegex = {
            'wiley': [re.compile(r"""<meta name=["']citation_publisher["']\s+content=["'](.+?)["']\s*/?>"""),
                      "John Wiley"],
            'elsevier': [re.compile(r"""<input type="hidden" name="redirectURL" value="https%3A%2F%2Fwww.sciencedirect.com%2Fscience%2Farticle%2Fpii%2F(.+?)%3Fvia%253Dihub" id="redirectURL"/>"""),
                         ""],
            'tandf': [re.compile(r"""<meta name=["']dc.Publisher["']\s+content=["'](.+?)["']\s*/?>"""),
                      "Taylor"],
            'annrev': [re.compile(r"""<meta name=["']dc.Publisher["']\s+content=["'](.+?)["']\s*/?>"""),
                       "Annual Reviews"],
            'rsc': [re.compile(r"""<meta content=["']https://pubs.rsc.org/en/content/articlepdf/(.+?)["']\s+name="citation_pdf_url"\s*/>"""),
                    ""],
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

        # Create a new ClientSession if one wasn't provided
        if client_session is None:
            # Make sure we have a polite header, though.
            session = aiohttp.ClientSession(headers=_g.httpHeaders)
        else:
            session = client_session
        try:
            async with session.get(doi_url) as resp:
                # Shortcut for ACS, don't need to read content
                if any("pubs.acs.org" in h
                       for h in resp.headers.getall("Set-Cookie", [])):
                    publisher = "acs"
                    identifier = self.doi
                    raise _PublisherFound
                # Shortcut for Nature, don't need to read content
                elif any("www.nature.com" in h
                         for h in resp.headers.getall("X-Forwarded-Host", [])):
                    publisher = "nature"
                    identifier = self.doi.split('/', maxsplit=1)[1]
                    raise _PublisherFound
                # Shortcut for Science, don't need to read content.
                # Note that this doesn't work for Sci Advances
                elif any("science.sciencemag.org" in h
                         for h in resp.headers.getall("Link", [])):
                    publisher = "science"
                    identifier = resp.headers["Link"].split(">")[0].split("/content/")[1]
                    raise _PublisherFound
                # Shortcut for Springer
                elif any(".springer.com" in h
                         for h in resp.headers.getall("Set-Cookie", [])):
                    publisher = "springer"
                    identifier = self.doi
                    raise _PublisherFound
                # Shortcut for Taylor and Francis
                elif any(".tandfonline.com" in h
                         for h in resp.headers.getall("Set-Cookie", [])):
                    publisher = "tandf"
                    identifier = self.doi
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
                                    identifier = self.doi
                                elif publisher in ["elsevier"]:
                                    identifier = match.group(1)
                                elif publisher in ["rsc"]:
                                    identifier = match.group(1)
                                raise _PublisherFound
        except (aiohttp.client_exceptions.ContentTypeError,
                aiohttp.client_exceptions.InvalidURL,
                aiohttp.client_exceptions.ClientConnectorError):
            result = _error(f"to_full_pdf_url: URL '{url_doi}' not accessible."
                            f" Do you have access to the full text?")
        except _PublisherFound:
            result = publisherFmtStrings[publisher].format(identifier)
        else:
            result = _error(f"to_full_pdf_url: could not find full text for "
                            f"doi {self.doi}")

        # Close the ClientSession if it was newly opened
        if client_session is None:
            await session.close()
        return result

    @staticmethod
    def from_pdf(path):
        """
        Tries to extract a DOI from a PDF file. Returns _ret.FAILURE if it
        can't.

        This method is fairly crude. It just utilises strings(1) and some magic
        regexes.

        Parameters
        ----------
        path : str or pathlib.Path
            Path to the PDF file. Best obtained by using parse_paths which does
            all the fiddly processing of escaped spaces etc.

        Returns
        -------
        DOI class instance. The actual DOI can be accessed as the doi attribute.
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
            return _error(f"from_pdf: invalid path '{p}' given")

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
            return DOI(doi)
        else:
            return _error(f"from_pdf: could not find DOI from '{p}'")


class Spinner():
    """
    Asynchronous context manager that can start and stop a spinner.

    async with Spinner(message, total, ...) as spinner:
        # code goes here
        spinner.increment()   # if needed
    """

    def __init__(self, message, total, units="", fstr="{}"):
        """
        message (str) - the message to display to the user while it's running
        total (float) - the number of tasks to run, or the number that it
                        should show when completed
        units (str)   - the units by which progress is measured
        fstr (str)    - a format string which 'done' and 'total' should be
                        formatted into. That is to say, the spinner's message
                        includes fstr.format(done) and fstr.format(total).
                        Defaults to '{}', i.e. default formatting.
        """
        self.message = message
        self.total = total
        self.units = units
        self.fstr = fstr
        self.done = 0      # running counter of tasks done
        self.time = 0      # time taken to run the tasks

    async def __aenter__(self):
        self.task = asyncio.create_task(self.run())
        return self

    async def run(self):
        write = sys.stdout.write
        flush = sys.stdout.flush
        try:
            for c in cycle("|/-\\"):
                full_message = (f"{c} {self.message} "
                                f"({self.fstr.format(self.done)}/"
                                f"{self.fstr.format(self.total)}"
                                f"{self.units})")
                write(full_message)
                flush()
                await asyncio.sleep(0.1)
                self.time += 0.1
                write('\x08' * len(full_message))
                flush()
        except asyncio.CancelledError:
            write('\x08' * len(full_message))
            flush()
            full_message = (f"- {self.message} "
                            f"({self.fstr.format(self.total)}/"
                            f"{self.fstr.format(self.total)}"
                            f"{self.units})")
            write(full_message)
            print()

    def increment(self, inc):
        """
        Increments the spinner's progress counter.
        """
        self.done += inc

    async def __aexit__(self, exc_type, exc_value, traceback):
        self.task.cancel()
        # We make sure that self.task is really cancelled before exiting, or
        # else it can mess up subsequent output quite badly.
        try:
            await self.task
        except asyncio.CancelledError:  # ok, it's really done
            pass
