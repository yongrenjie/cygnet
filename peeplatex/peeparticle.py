"""
peeparticle.py
--------------

Contains the Article class and methods on it.
Also contains methods for generating an Article from a DOI using the Crossref API.
"""

import asyncio
from unicodedata import normalize

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

    def format_authors(self, style):
        """
        Convert author names to a suitable format.

        Arguments:
            style (str)   : Style in which the output should be produced. Must
                            be one of "display", "acs", or "bib". The output is
                            as follows:
                             - "display": "JRJ Yong"
                             - "acs"    : "Yong, J. R. J."
                             - "bib"    : "Yong, Jonathan R. J."

        Returns:
            A list of appropriately formatted strings, one for each author.

        Raises:
            ValueError if the requested style does not exist.
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
            # Otherwise, grumble.
            else:
                raise ValueError(f"Invalid value '{style}' for style.")

        return [format_one_author(author, style) for author in self.authors]

    def format_short_journalname(self):
        """
        Extracts the short journal name from an article and tries to make it as
        short as possible, e.g. by removing periods as well as using some
        acronyms like "NMR".

        Returns:
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
        """
        if self.issue != "":
            return "{} ({}), {}".format(self.volume,
                                        self.issue,
                                        self.pages)
        else:
            return "{}, {}".format(self.volume,
                                   self.pages)

    def get_availability_string(self):
        """
        Generates a string reflecting the presence or absence of a PDF or SI
        for a given article.

        Returns:
            A string with a green tick / red cross for 'pdf' and 'si' formats.
        """
        types = ["pdf", "si"]
        paths = [self.to_fname(type) for type in types]
        symbols = ['\u2714' if path.is_file() else '\u2718'
                   for path in paths]
        colors = [_g.ansiDiffGreen if path.is_file() else _g.ansiDiffRed
                  for path in paths]
        return (f"{colors[0]}{symbols[0]}{_g.ansiReset}pdf  "
                f"{colors[1]}{symbols[1]}{_g.ansiReset}si")

    def to_fname(self, type):
        """
        Converts a given article to a filename or URL. Filenames are absolute,
        constructed using _g.currentPath.

        Arguments:
            type (str) : "pdf", "si", or "web". The abbreviations "p", "s", and
                         "w" are allowed as well.

        Returns:
            The filename or URL as a string.

        Raises:
            ValueError if the type parameter is not one of the above.
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

        Arguments:
            type (str) : "bib", "markdown", "Markdown", "doi", or "word". The
                         abbreviations "b", "m", "M", "d", and "w" are also
                         allowed.

        Returns:
            The citation as a string.

        Raises:
            ValueError if the type parameter is not one of the above.
        """
        acs_authors = ";".join(self.format_authors("acs"))
        pages_with_endash = self.pages.replace("-", "\u2013")
        # Just DOI
        if type in ["doi", "d"]:
            return self.doi

        # Markdown short
        elif type in ["markdown", "m"]:
            if self.issue is not None:
                return (f"*{self.journal_short}* **{self.year}**, "
                        f"*{self.volume}* ({self.issue}), "
                        f"{pages_with_endash}. "
                        f"[DOI: {self.doi}](https://doi.org/{self.doi}).")
            else:
                return (f"*{self.journal_short}* **{self.year}**, "
                        f"*{self.volume},* "
                        f"{pages_with_endash}. "
                        f"[DOI: {self.doi}](https://doi.org/{self.doi}).")

        # Markdown long
        elif type in ["Markdown", "M"]:
            if self.issue is not None:
                return (f"{acs_authors} {self.title}. "
                        f"*{self.journal_short}* **{self.year}**, "
                        f"*{self.volume}* ({self.issue}), "
                        f"{pages_with_endash}. "
                        f"[DOI: {self.doi}](https://doi.org/{self.doi}).")
            else:
                return (f"{acs_authors} {self.title}. "
                        f"*{self.journal_short}* **{self.year}**, "
                        f"*{self.volume},* "
                        f"{pages_with_endash}. "
                        f"[DOI: {self.doi}](https://doi.org/{self.doi}).")

        # Word
        elif type in ["word", "w"]:
            if self.issue is not None:
                return (f"{acs_authors}"
                        f"{self.journal_short} {self.year}, "
                        f"{self.volume} ({self.issue}), "
                        f"{pages_with_endash}.")
            else:
                return (f"{acs_authors}"
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


def doi_to_citation(doi, type):
    """
    Generates a citation from a DOI via an Article instance.

    Arguments:
        doi (str)  : DOI to look up.
        type (str) : "bib", "markdown", "Markdown", "doi", or "word". The
                     abbreviations "b", "m", "M", "d", and "w" are also
                     allowed.
    """
    return doi_to_article(doi).to_citation(type)


def doi_to_article(doi):
    """
    Blocking version of to_article_cr(). Useful as an external API as then
    the user need not worry about using asyncio.

    Arguments:
        doi (str) : DOI to look up.

    Returns:
        Article instance if lookup was successful.

    Raises:
        ValueError if the DOI was invalid.
    """
    article = asyncio.run(doi_to_article_cr(doi))
    if article.title is None:
        raise ValueError(f"Invalid DOI '{doi}' given.")
    else:
        return article


async def doi_to_article_cr(doi, client_session=None):
    """
    Uses Crossref API to obtain article metadata using a DOI. Returns a
    dictionary that is immediately suitable for use in _g.articleList.

    Incorrect journal short forms are corrected here. The dictionary containing
    the corrections is stored in _g.

    This can optionally be be passed an aiohttp.HTTPSession instance together
    with the actual DOI. If not, then a new HTTPSession is generated.

    Arguments:
        doi (str)                            : DOI to look up.
        client_session (aiohttp.HTTPSession) : aiohttp session instance to use.

    Returns:
        Article instance. If the lookup was successful, all the Article fields
        will be populated. If not, then all fields will be None, except for the
        DOI field, which will contain the DOI that was looked up.
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
        article = Article(doi=doi)
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

        try:
            article.volume = int(d["volume"])
        except KeyError:   # no volume
            article.volume = ""
        except ValueError:  # it's a range (!!!)
            article.volume = d["volume"]
        try:
            article.issue = int(d["issue"])
        except KeyError:   # no issue
            article.issue = ""
        except ValueError:  # it's a range (!!!)
            article.issue = d["issue"]
        article.pages = d["page"] if "page" in d else ""
    finally:
        # If the ClientSession instance wasn't provided, close it.
        if client_session is None:
            await session.close()

    # We can't put the return inside the finally, because exceptions that occur
    # in the else block are only raised *after* the finally block. So, if the
    # return is placed inside finally, exceptions are never raised.
    return article
