"""
commands.py
-----------

Functions which the command line calls. These should NOT be used by other
functions in the programme, as the interface is designed SOLELY for command
line usage!
"""

import re
import subprocess
import shutil
import asyncio
from pathlib import Path
from copy import deepcopy
from datetime import datetime, timezone
from tempfile import NamedTemporaryFile
from operator import attrgetter

import yaml
import prompt_toolkit as pt

from . import fileio
from . import listprint
from . import backup
from .peepcls import Article, DOI, Spinner
from ._shared import *


@_helpdeco
def cli_cd(args):
    """
    *** cd ***

    Usage
    -----
    cd [directory]

    Description
    -----------
    Changes the current working directory to the given directory, then attempts
    to read in a database from a peep.yaml file.

    When a new database is read in, the references will be sorted by year. The
    undo history will also be cleared.
    """
    # Check for plain 'cd' which goes back to home directory.
    if args == []:
        p = Path.home()
    # Check for 'cd -' which goes to previous path.
    elif args == ["-"]:
        if _g.previousPath is None:
            return _error(f"cd: previous path not set")
        else:
            p = _g.previousPath
    # Otherwise, parse the arguments and take only the first
    else:
        try:
            p = parse_paths(args)[0]
        except ArgumentError as e:
            return _error(f"cd: {str(e)}")

    if not p.is_dir():
        return _error(f"cd: directory {p} does not exist")

    # If it is the same file, don't bother doing anything
    if p == _g.currentPath:
        return

    # Otherwise, save the previous article list first (if there is any)
    if _g.articleList and _g.currentPath and _g.changes != []:
        _g.changes = []
        fileio.write_articles(_g.articleList, _g.currentPath / "peep.yaml")

    # Change the path
    _g.previousPath, _g.currentPath = _g.currentPath, p.resolve()

    # Try to read in the yaml file, if it exists
    try:
        new_articles = fileio.read_articles(p / "peep.yaml")
    except yaml.YAMLError:
        _error(f"cd: A peep.yaml file was found in {p}, "
               "but it contained invalid YAML.")
    except FileNotFoundError:
        # Clear out existing articles, if any
        _g.articleList = []
    else:
        # Load those new articles
        _g.articleList = new_articles
        backup.createBackup()
        _sort.sort()  # sort according to currently active mode
    finally:
        _clearHist()
        return _ret.SUCCESS


@_helpdeco
def cli_write(args):
    """
    *** write ***

    Usage
    -----
    w[rite]

    Description
    -----------
    Saves the current database to the current working directory.

    Note that changes are automatically saved every few seconds. This means
    that in practice the need for this function should not arise often.
    """
    if _g.articleList != []:
        fileio.write_articles(_g.articleList, _g.currentPath / "peep.yaml")
        _g.changes = []
    else:
        return _error("write: no articles loaded")
    return _ret.SUCCESS


@_helpdeco
def cli_list(args):
    """
    *** list ***

    Usage
    -----
    l[ist] [-l] [refnos]

    Description
    -----------
    Lists articles in the currently loaded database. If no further reference
    numbers are specified, lists all articles. Also prints information about
    whether the full text PDF and the SI are stored in the database.

    Reference numbers may be specified as a comma- or space-separated series of
    integers or ranges (low-high, inclusive). For example, 'l 41-43' lists
    articles 41 through 43. 'l 4, 9, 21-24' lists articles 4, 9, and 21 through
    24. 'all' can be used as a shortcut for every reference number.

    By default, the list of authors in each article is truncated such that they
    occupy at most 5 lines. To prevent this behaviour, pass the "-l" flag.
    """
    if _g.articleList == []:
        return _error("list: no articles found")

    # Check for (potentially multiple) '-l' arguments
    max_auth = 0 if "-l" in args else 5
    while "-l" in args:
        args.remove("-l")

    # Parse remaining arguments as refnos
    try:
        refnos = parse_refnos(args)
    except ArgumentError as e:
        return _error(f"list: {str(e)}")
    # If no refnos provided, then assume all
    if len(refnos) == 0:
        refnos = set(range(1, len(_g.articleList) + 1))

    # Pick out the desired references. No need to make a copy because
    # print_list() does it for us.
    articles = [_g.articleList[r - 1] for r in refnos]

    # Now print it
    try:
        listprint.print_list(articles, refnos, max_auth)
    except ValueError as e:
        return _error(f"list: {str(e)}")


@_helpdeco
def cli_search(args):
    """
    *** search ***

    Usage
    -----
    s[earch] query[...]

    Description
    -----------
    Performs a case-insensitive search for articles whose authors or titles
    contain the given queries, then lists articles which were found. Special
    characters are converted to ASCII equivalents, so a search for "jose" will
    also match papers written by "José".

    If more than one query is given, will attempt to find articles containing
    ALL queries. If none are found, then will return a list of articles
    containing at least one of the queries.

    VERY crude.
    """
    result_flag = "NONE"   # means no articles were found.

    # the arguments are entered by the user. We use re.compile() to turn them
    # into regexes.
    queries = [re.compile(arg, flags=re.IGNORECASE) for arg in args]
    found_refnos = []
    for refno, article in enumerate(_g.articleList, start=1):
        if all(article.search(*queries)):
            # all queries were found.
            found_refnos.append(refno)
            result_flag = "ALL"
            # means articles were found matching all queries

    if found_refnos == [] and len(queries) > 1:
        # loosen search criteria. Just look for at least one query, instead of
        # all.
        for refno, article in enumerate(_g.articleList, start=1):
            if any(article.search(*queries)):
                found_refnos.append(refno)
                result_flag = "ANY"
                # means articles were found matching at least one query

    # if any articles were found...
    if len(found_refnos) > 0:
        found_articles = [_g.articleList[r - 1] for r in found_refnos]
        listprint.print_list(found_articles, found_refnos, max_auth=0)
    # let the user know accordingly
    if result_flag == "NONE":
        print(f"{_g.ansiTitleBlue}search: no articles matching the search"
              f" query were found{_g.ansiReset}")
    elif result_flag == "ANY":
        print(f"{_g.ansiTitleBlue}search: {len(found_refnos)}"
              f" article{_p(found_refnos)} matching at least one search query"
              f" {_p(found_refnos, 'was', 'were')} found{_g.ansiReset}")
    elif result_flag == "ALL" and len(queries) > 1:
        print(f"{_g.ansiTitleBlue}search: {len(found_refnos)}"
              f" article{_p(found_refnos)} matching all search queries"
              f" {_p(found_refnos, 'was', 'were')} found{_g.ansiReset}")
    elif result_flag == "ALL" and len(queries) == 1:
        print(f"{_g.ansiTitleBlue}search: {len(found_refnos)}"
              f" article{_p(found_refnos)} matching the search query"
              f" {_p(found_refnos, 'was', 'were')} found{_g.ansiReset}")


@_helpdeco
def cli_open(args):
    """
    *** open ***

    Usage
    -----
    o[pen] refno[...] [formats]

    Description
    -----------
    Opens the original text of one or more references.

    At least one refno must be specified. For more details about the format in
    which refnos are specified, type 'h list'.

    More than one format can be provided, separated by commas, spaces, or even
    by nothing at all. Available formats are:

        'pdf' or 'p' (default) - The full text of the article (as a PDF).
        'si'  or 's'           - The SI of the article (as a PDF).
        'web' or 'w'           - The website.

    If the PDFs are not present in the relevant folder, they can be added using
    the 'ap' command.
    """
    # Argument parsing
    if _g.articleList == []:
        return _error("open: no articles have been loaded")
    if args == []:
        return _error("open: no references selected")
    abbrevs = {"p": "pdf",
               "s": "si",
               "w": "web"}
    try:
        refnos, formats = parse_refnos_formats(args, abbrevs=abbrevs)
    except ArgumentError as e:
        return _error(f"open: {str(e)}")
    if len(refnos) == 0:
        return _error("open: no references selected")

    # Default format -- PDF
    if formats == []:
        formats = ['p']

    # Open the references
    yes, no = 0, 0
    for refno in refnos:
        article = _g.articleList[refno - 1]
        for format in formats:
            try:
                path = article.to_fname(format)
            except ValueError as e:  # invalid format
                _error(f"open: invalid format '{format}' given")
                no += 1
                continue
            # Error checking
            if format == "p":
                if not path.is_file():
                    _error(f"open: ref {refno}: PDF file {path} not found")
                    no += 1
                    continue
            elif format == "s":
                if not path.is_file():
                    _error(f"open: ref {refno}: SI file {path} not found")
                    no += 1
                    continue
            # Open it using open(1)
            try:
                subprocess.run(["open", path], check=True, capture_output=True)
            except subprocess.CalledProcessError:
                _error("open: ref {refno}: error opening file/URL {path}")
                no += 1
            else:
                yes += 1
                # Update time opened of article.
                article.time_opened = datetime.now(timezone.utc)

    print(f"open: {yes} references opened, {no} failed")
    _g.changes += ["open"] * yes
    return _ret.SUCCESS


@_helpdeco
async def cli_cite(args):
    """
    *** cite ***

    Usage
    -----
    c[ite] refno[...] [formats]

    Description
    -----------
    Provides a citation for one or more references. Also copies the citation
    text to the clipboard.

    At least one refno must be specified. For more details about the format in
    which refnos are specified, type 'h list'.

    More than one format can be provided, separated by commas, spaces, or even
    by nothing at all. Available formats are:

        'bib' or 'b' (default) - BibLaTeX. The article identifier is
                                 constructed by concatenating the first author,
                                 year, and journal.
        'doi' or 'd'           - Just the DOI.

    For the following formats, the first letter can also be capitalised in
    order to include author names. For example, 'Rst' or 'R' will give the
    reStructuredText citation with author names. Unless otherwise specified,
    all of these output citations according to the ACS Style Guide.

        'rst' or 'r'           - reStructuredText.
        'markdown' or 'm'      - Markdown.
        'word' or 'w'          - A suitable style for Microsoft Word (but no
                                 formatting such as bold/italics).

    """
    # Argument parsing
    if _g.articleList == []:
        return _error("cite: no articles have been loaded")
    if args == []:
        return _error("cite: no references selected")
    abbrevs = {"d": "doi",
               "b": "bib",
               "m": "markdown",
               "M": "Markdown",
               "w": "word"}
    try:
        refnos, formats = parse_refnos_formats(args)
    except ArgumentError as e:
        return _error(f"cite: {str(e)}")
    # Check the returned values
    if len(refnos) == 0:
        return _error("cite: no references selected")

    # Default format = biblatex
    if formats == []:
        formats = ['b']

    cite_list = []
    for refno in refnos:
        article = _g.articleList[refno - 1]
        for format in formats:
            try:
                citation = article.to_citation(format)
            except ValueError as e:  # invalid format
                _error(f"cite: invalid format '{format}' given")
                continue
            else:
                cite_list.append(citation)

    citations = "\n\n".join(cite_list)
    if citations.strip() != "":
        print(citations)
        await _copy(citations)
    return _ret.SUCCESS


@_helpdeco
def cli_edit(args):
    """
    *** edit ***

    Usage
    -----
    e[dit] refno[...]

    Description
    -----------
    Directly edit the entries for one or more citations, using vim. To cancel
    any changes made, exit vim using :cq.

    At least one refno must be specified. For more details about the format in
    which refnos are specified, type 'h list'.
    """
    # Argument parsing
    if _g.articleList == []:
        return _error("edit: no articles have been loaded")
    if args == []:
        return _error("edit: no references selected")

    try:
        refnos = parse_refnos(args)
    except ArgumentError as e:
        return _error(f"edit: {str(e)}")
    if len(refnos) == 0:
        return _error("edit: no references selected")

    # Create and write data to temp file.
    # Suffix is needed so that vim syntax highlighting is enabled. :)
    tempfile = Path(NamedTemporaryFile(suffix=".yaml").name)
    articles_to_edit = [_g.articleList[r - 1] for r in refnos]
    fileio.write_articles(articles_to_edit, tempfile)
    # Open the file in vim. Vim's stdin and stdout need to be from/to a tty.
    # This is already the case for stdin, but we need to set stdout manually.
    try:
        subprocess.run(["vim", str(tempfile)],
                       stdout=open('/dev/tty', 'wb'),
                       check=True)
    except subprocess.CalledProcessError:   # e.g. :cq
        return _error("edit: vim quit unexpectedly; no changes made")
    else:
        # Put the edited metadata back in the article list and trigger autosave
        try:
            edited_articles = fileio.read_articles(tempfile)
        except yaml.YAMLError:
            return _error("edit: invalid YAML syntax for PeepLaTeX "
                          "articles")
        for (edited_article, refno) in zip(edited_articles, refnos):
            # Before replacing it, make sure that the PDF/SIs are moved to the
            # correct location!!
            types = ["pdf", "si"]
            old_fnames = [_g.articleList[refno - 1].to_fname(t) for t in types]
            new_fnames = [edited_article.to_fname(t) for t in types]
            for old_fname, new_fname in zip(old_fnames, new_fnames):
                if old_fname.is_file():
                    old_fname.rename(new_fname)
            # Ok, now we can replace it
            _g.articleList[refno - 1] = edited_article
            _g.changes += ["edit"]
        return _ret.SUCCESS


@_helpdeco
async def cli_add(args):
    """
    *** add ***

    Usage
    -----
    a[dd] DOI[...]

    Description
    -----------
    Adds one or more DOIs to the reference list. Separate DOIs must be
    separated by spaces. After the reference is added, the list is sorted
    again using the currently active sorting method.

    Uses the Crossref API to obtain metadata about an article.
    """
    # TODO automatically try to fetch pdf???

    # Argument parsing
    if args == []:
        return _error("addRef: no DOIs provided")
    yes = 0
    no = 0
    # Check if any are already in the library
    dois = []
    for doi in args:
        found = False
        for refno, article in enumerate(_g.articleList, start=1):
            if doi == article.doi:
                found = True
                break
        if found:
            _error(f"add: DOI '{doi}' already in library.\n"
                   f"            Use 'u[pdate] {refno}' to refresh metadata.")
            no += 1
        else:
            dois.append(doi)
    if dois == []:
        return

    articles = []
    coroutines = [DOI(doi).to_article_cr(_g.ahSession)
                  for doi in dois]
    async with Spinner(message="Fetching metadata...",
                       total=len(dois)) as spinner:
        for crt in asyncio.as_completed(coroutines):
            articles.append(await crt)
            spinner.increment(1)

    for article in articles:
        # Check for failure
        if article.title is None:
            _error(f"add: invalid DOI '{article.doi}'")
            no += 1
            continue
        else:
            article.time_added = datetime.now(timezone.utc)
            article.time_opened = datetime.now(timezone.utc)
            # Prompt user whether to accept the article
            empty_article = Article()
            empty_article.diff(article)
            msg = "add: accept new data (y/n)? ".format()
            style = pt.styles.Style.from_dict({"prompt": _g.ptBlue, "":
                                               _g.ptGreen})
            try:
                ans = await pt.PromptSession().prompt_async(msg, style=style)
            except (EOFError, KeyboardInterrupt):
                ans = "no"
            if ans.strip().lower() in ["", "y", "yes"]:
                _g.articleList.append(article)
                print(f"add: added DOI {article.doi}")
                yes += 1
            else:
                print(f"add: DOI {article.doi} not added")
                no += 1

    print(f"add: {yes} DOIs added, {no} failed")
    _g.changes += ["add"] * yes
    _sort.sort()  # Sort according to the currently active mode
    return yes, no


@_helpdeco
def cli_sort(args):
    """
    *** sort ***

    Usage
    -----
    so[rt] [mode]

    Sorts the currently loaded database. The key by which to sort can be
    passed as the only option. The available modes are:

        "year", "yja", or "y"     - first by year, then journal name, then
                                    first author surname
        "opened", "open", or "o"  - by the time last opened
        "added", "add", or "a"    - by the time added to the database

    If no key is used, then the current sorting mode is used. When loading
    an article, this will always be "year", but when calling 'so <key>', the
    requested key will be stored as the current sorting mode.

    To query the current sorting mode, use `so[rt] ?`.

    By default, articles are sorted from oldest to newest, such that the most
    recent articles always appear at the bottom of the list (i.e. easiest to
    see). Reverse sort can be performed by capitalising the first letter of
    the key passed as a command-line argument, e.g. 'so Y' to sort from newest
    to oldest.
    """
    # Argument parsing
    if _g.articleList == []:
        return _error("sort: no articles have been loaded")
    if args == []:
        mode, reverse = None, None
    elif args[0] == "?":
        print(_sort.mode + (", reverse" if _sort.reverse else ""))
        return _ret.SUCCESS
    else:
        # Pick out capital letter, then convert to lowercase
        reverse = True if args[0][0].isupper() else False
        args[0] = args[0].lower()
        # Choose sorting mode
        if args[0] in ["y", "ye", "yea", "year"]:
            mode = "year"
        elif args[0] in ["o", "op", "ope", "open", "opened", "timeopened"]:
            mode = "time_opened"
        elif args[0] in ["a", "ad", "add", "added", "timeadded"]:
            mode = "time_added"
        else:
            mode = args[0]
    # Sort
    try:
        _sort.sort(mode, reverse)
    except ValueError as e:   # invalid mode
        return _error(f"sort: {str(e)}")
    # Trigger autosave
    _g.changes += ["sort"]
    return _ret.SUCCESS


@_helpdeco
async def cli_update(args):
    """
    *** update ***

    Usage
    -----
    u[pdate] refno[...]

    Description
    -----------
    Update one or more references using the Crossref API. If any differences in
    the metadata are detected, then the user is prompted to accept or reject
    the changes before applying them to the database.

    At least one refno must be specified. For more details about the format in
    which refnos are specified, type 'h list'.
    """
    # Argument processing
    if _g.articleList == []:
        return _error("update: no articles have been loaded")
    try:
        refnos = parse_refnos(args)
    except ArgumentError as e:
        return _error(f"update: {str(e)}")
    if len(refnos) == 0:
        return _error("update: no references selected")

    # Lists containing old and new Articles. Since data is being pulled
    # asynchronously, we need to be careful with the sorting. Throughout this
    # section we sort every list by the DOIs.
    old_articles = [_g.articleList[r - 1] for r in refnos]
    old_articles, refnos = zip(*sorted(zip(old_articles, refnos),
                                       key=(lambda t: t[0].doi)))
    crts = [article.to_newarticle_cr(_g.ahSession) for article in old_articles]
    new_articles = []
    # Perform asynchronous HTTP requests
    async with Spinner(message="Fetching metadata...",
                       total=len(refnos)) as spinner:
        for crt in asyncio.as_completed(crts):
            new_articles.append(await crt)
            spinner.increment(1)
    # After we finish pulling the new Articles, they are out of order. We can
    # sort the new Articles by DOI to get the same ordering as the old Articles
    # and refnos.
    new_articles.sort(key=attrgetter("doi"))
    # Now we sort everything by refnos so that we can present them nicely to
    # the user.
    refnos, old_articles, new_articles = zip(*sorted(zip(refnos,
                                                         old_articles,
                                                         new_articles)))

    # Present them one by one to the user
    yes = 0
    for refno, old_article, new_article in zip(refnos,
                                               old_articles,
                                               new_articles):
        if new_article.title is None:
            _error(f"update: ref {refno} has invalid DOI '{old_article.doi}'")
            continue
        # copy over timeAdded, timeOpened data from old reference
        new_article.time_added = old_article.time_added
        new_article.time_opened = old_article.time_opened
        # calculate and report differences
        ndiffs = old_article.diff(new_article)
        if ndiffs == 0:
            print(f"update: ref {refno}: no new data found")
        else:
            msg = f"update: ref {refno}: accept new data? (y/n) "
            style = pt.styles.Style.from_dict({"prompt": _g.ptBlue,
                                               "": _g.ptGreen})
            try:
                ans = await pt.PromptSession().prompt_async(msg, style=style)
            except (EOFError, KeyboardInterrupt):
                ans = "no"
            if ans.strip().lower() in ["", "y", "yes"]:
                _g.articleList[refno - 1] = new_article
                print(f"update: ref {refno}: successfully updated")
                yes += 1
            else:  # ok, it isn't really (y/n), it's (y/not y)
                print(f"update: ref {refno}: changes rejected")
    print(f"update: {yes} article{_p(yes)} updated")
    _g.changes += ["update"] * yes
    return _ret.SUCCESS


@_helpdeco
async def cli_delete(args):
    """
    *** delete ***

    Usage
    -----
    d[elete] refno[...]

    Description
    -----------
    Deletes one or more references, as well as the PDFs associated with them.
    """
    # Argument parsing
    if _g.articleList == []:
        return _error("delete: no articles have been loaded")
    if args == []:
        return _error("deleteRef: no references selected")
    try:
        refnos = parse_refnos(args)
    except ArgumentError as e:
        return _error(f"delete: {str(e)}")
    if len(refnos) == 0:
        return _error("delete: no references selected")

    # Must use a new PromptSession().prompt_async(), otherwise it gets messed up.
    yes = 0
    msg = (f"delete: really delete ref{_p(refnos)} "
           f"{', '.join(str(r) for r in refnos)} (y/n)? ")
    style = pt.styles.Style.from_dict({"prompt": _g.ptBlue,
                                       "": _g.ptGreen})
    try:
        ans = await pt.PromptSession().prompt_async(msg, style=style)
    except (EOFError, KeyboardInterrupt):
        ans = "no"
    if ans.strip().lower() in ["", "y", "yes"]:
        # Sort refnos in descending order so that we don't have earlier
        # deletions affecting later ones!!!
        refnos.sort(reverse=True)
        for refno in refnos:
            article = _g.articleList[refno - 1]
            # Delete the PDFs first
            pdf_paths = [article.to_fname(type) for type in ("pdf", "si")]
            for pdf in pdf_paths:
                pdf.unlink(missing_ok=True)
            # Then delete the article
            del _g.articleList[refno - 1]
            yes += 1
        print(f"delete: {yes} ref{_p(yes)} deleted")
        _g.changes += ["delete"] * yes
    else:
        print("delete: no refs deleted")
    return _ret.SUCCESS


@_helpdeco
async def cli_import(args=None):
    """
    *** import ***

    Usage
    -----
    i[mport] path[...]

    Description
    -----------
    Import a PDF into the database. Automatically attempts to detect the DOI
    from the PDF and fetch the corresponding metadata. The paths provided can
    either be single PDF files, or folders containing multiple PDF files.
    (Note that directories are not searched recursively.)

    If this fails, add the DOI manually (with 'a <doi>'), then add the
    PDF with 'ap <refno>'.
    """
    # Argument processing
    if args == []:
        return _error("import: no path(s) provided")

    # Get paths from the args.
    paths = parse_paths(args)
    # Find directories and get files from them
    dirs = [p for p in paths if p.is_dir()]
    files = [p for p in paths if p.is_file()]
    for dir in dirs:
        files += [f for f in dir.iterdir() if f.suffix == ".pdf"]

    yes, no = 0, 0
    # Process every PDF file found.
    for file in files:
        # Try to get the DOI (as a string, hence the .doi at the end)
        doi = DOI.from_pdf(file).doi
        if doi == _ret.FAILURE:
            no += 1
        else:
            print(f"import: detected DOI {doi} for PDF '{file}'")
            # Check whether it's already in the database
            for refno, article in enumerate(_g.articleList, start=1):
                if doi == article.doi:
                    _error(f"import: DOI {doi} already in database. Use 'ap "
                           f"{refno}' to associate this PDF with it.")
                    no += 1
                    break
            else:
                # Prompt user whether they want to add it
                # The fastest way is to call cli_add.
                addyes, addno = await cli_add([doi])
                yes += addyes
                no += addno
                if addyes == 1:
                    # Save the pdf into the database.
                    psrc = file
                    pdest = DOI(doi).to_article(metadata=False).to_fname("pdf")
                    # mkdir -p the folder if it doesn't already exist.
                    if not pdest.parent.exists():
                        pdest.parent.mkdir(parents=True)
                    shutil.copy2(psrc, pdest)
    # Trigger autosave
    _g.changes += ["import"] * yes
    return yes, no


@_helpdeco
async def cli_addpdf(args):
    """
    *** addpdf ***

    Usage
    -----
    addpdf refno[...] [formats]
    ap refno[...] [formats]

    Description
    -----------
    Add a PDF to an existing reference in the database. Arguments can be
    provided as refnos; see 'h list' for more details on the syntax. The
    available formats are "pdf" (or "p"), and "si" (or "s"). If no formats are
    provided then defaults to both.

    This function will then prompt you for a link to the file; this can be
    provided as either a URL or an (absolute) file system path. File paths can
    be most easily provided by dragging-and-dropping a file into the terminal
    window.

    Note that PDFs that have already been saved cannot be changed using this
    command. You have to delete the PDF first (using 'dp'), then re-add the new
    PDF.
    """
    if _g.articleList == []:
        return _error("addpdf: no articles have been loaded")

    abbrevs = {"pdf": "p", "si": "s"}
    try:
        refnos, formats = parse_refnos_formats(args, abbrevs=abbrevs)
    except ArgumentError as e:
        return _error(f"addpdf: {str(e)}")
    if len(refnos) == 0:
        return _error("addpdf: no references selected")
    # apply default formats
    if len(formats) == 0:
        formats = ["p"]
    # expand to long form as we will need it later
    long_formats = []
    for k, v in abbrevs.items():
        if v in formats:
            long_formats.append(k)

    yes, no = 0, 0
    # We wrap the whole thing in try/except to catch Ctrl-C, which will get us
    # out of the entire loop quickly. Sending Ctrl-D just moves us to the next
    # refno.
    try:
        for i, r in enumerate(refnos):
            article = _g.articleList[r - 1]
            # Print a line break between successive references
            if i != 0:
                print()  # Just a bit easier to read.
            # Print the header to tell the user which article they're adding
            # to, as well as whether the PDFs are already available.
            print(f"{_g.ansiBold}({r}) {article.authors[0]['family']} "
                  f"{article.year}:{_g.ansiReset} {article.title}", end="   ")
            availability = article.get_availability()
            print(article.get_availability_string())

            style = pt.styles.Style.from_dict({"prompt": _g.ptBlue,
                                               "": _g.ptGreen})
            for fmt, avail in zip(["pdf", "si"], availability):
                # Check whether the format was requested
                if fmt not in long_formats:
                    continue
                # Check whether it's already available
                if avail:
                    print(f"{fmt.upper()} is already available.")
                    continue
                # If we reach here, then it's not available.
                try:
                    ans = await pt.PromptSession().prompt_async(
                        (f"addpdf: provide path to {fmt.upper()} (leave "
                         f"empty to skip): "),
                        style=style)
                except EOFError:  # move on to next question...
                    continue
                if ans.strip():
                    save_task = asyncio.create_task(
                        article.register_pdf(ans, fmt, _g.ahSession))
                    [done_task, ], _ = await asyncio.wait([save_task])
                    if done_task.result() == _ret.SUCCESS:
                        yes += 1
                    else:
                        no += 1
    except KeyboardInterrupt:
        pass

    print("addpdf: {} PDFs added, {} failed".format(yes, no))
    return _ret.SUCCESS


@_helpdeco
async def cli_deletepdf(args):
    """
    *** deletepdf ***

    Usage
    -----
    deletepdf refno[...] [formats]
    dp refno[...] [formats]

    Description
    -----------
    Delete a PDF from an existing reference in the database. The articles for
    which PDFs should be deleted are specified as refnos; see 'h list' for more
    details on the syntax.

    This does NOT prompt for confirmation!

    More than one format can be provided, separated by commas, spaces, or even
    by nothing at all. Available formats are:

        'pdf' or 'p' (default) - The full text of the article (as a PDF).
        'si'  or 's'           - The SI of the article (as a PDF).
    """
    if _g.articleList == []:
        return _error("deletepdf: no articles have been loaded")

    abbrevs = {"pdf": "p", "si": "s"}
    try:
        refnos, formats = parse_refnos_formats(args, abbrevs=abbrevs)
    except argumenterror as e:
        return _error(f"deletepdf: {str(e)}")
    if len(refnos) == 0:
        return _error("deletepdf: no references selected")
    # apply default formats
    if len(formats) == 0:
        formats = ["p"]

    # Just delete it, no questions asked!
    yes = 0
    for i, r in enumerate(refnos):
        article = _g.articleList[r - 1]
        for f in formats:
            fname = article.to_fname(f)
            if fname.exists():
                yes += 1
                fname.unlink()
    print(f"deletepdf: {yes} files deleted")
    return _ret.SUCCESS


@_helpdeco
async def cli_fetch(args):
    """
    *** fetch ***

    Usage
    -----
    f[etch] refno[...]

    Description
    -----------
    Attempts to find the URL, and download, the full text PDF for the specified
    refnos. For more information on how to specify refnos, type 'h list'.

    The heuristics used are hardcoded, so are not guaranteed to work on every
    DOI, and indeed even those that work now may break later. But the major
    publishers all work (for now). Supported publishers are: ACS, Wiley,
    Elsevier, Nature, Science, Springer, Taylor and Francis, and Annual
    Reviews (as of 27 May 2020).

    Note that in order to download the full-text PDF, institutional access must
    be enabled, e.g. via VPN. (Or, of course, the PDF must be open-access.)
    """
    # Argument parsing
    if _g.articleList == []:
        return _error("fetch: no articles have been loaded")
    if args == []:
        return _error("fetch: no references selected")

    try:
        refnos = parse_refnos(args)
    except ArgumentError as e:
        return _error(f"fetch: {str(e)}")
    if len(refnos) == 0:
        return _error("fetch: no references selected")

    # Check which ones need downloading
    articles_to_fetch = []
    for refno in refnos:
        article = _g.articleList[refno - 1]
        if not article.to_fname("pdf").exists():
            articles_to_fetch.append(article)
        else:
            print(f"fetch: PDF for ref {refno} already in library")

    yes, no = 0, 0
    if articles_to_fetch == []:
        return _ret.SUCCESS
    else:
        # Construct DOI objects.
        dois = [DOI(article.doi) for article in articles_to_fetch]
        async with Spinner(message="Obtaining URLs...",
                           total=len(dois)) as spinner:
            tasks = [asyncio.create_task(
                doi.to_full_pdf_url(client_session=_g.ahSession)
            ) for doi in dois]
            # We're just using as_completed() to update the spinner. We aren't
            # actually retrieving the results from here, because they are not
            # returned in order.
            for coro in asyncio.as_completed(tasks):
                await coro
                spinner.increment(1)
            # Now they should all be done, so we can retrieve the results.
            urls = [task.result() for task in tasks]

        for article, url in zip(articles_to_fetch, urls):
            if url == _ret.FAILURE:
                no += 1
            else:
                x = await article.register_pdf(url, "pdf", _g.ahSession)
                if x == _ret.FAILURE:
                    no += 1
                else:
                    yes += 1

    print("fetch: {} PDFs successfully fetched, {} failed".format(yes, no))
    return _ret.SUCCESS


class ArgumentError(Exception):
    """
    Exception indicating that something about the arguments was invalid.
    """
    pass


def parse_paths(args):
    """
    Takes a list of command-line arguments and returns a list of Path objects,
    one from each argument.
    """
    try:
        paths = [Path(arg) for arg in args]
    except TypeError:  # not castable
        raise ArgumentError(f"invalid argument{_p(args)} {args}")

    # Resolve relative to _g.currentPath
    for i, path in enumerate(paths):
        if not path.is_absolute():
            path = _g.currentPath / path
        # We need to actually replace paths[i], or else (I think) it creates a
        # new object that isn't in the list.
        paths[i] = path.resolve().expanduser()
    return paths


def parse_refnos(args):
    """
    Takes a list of arguments and returns a list of integer reference numbers.
     e.g. ['1']           -> [1]
          ['1-5']         -> [1, 2, 3, 4, 5]
          ['1-4', '43']   -> [1, 2, 3, 4, 43]
          ['1-4,6', '43'] -> [1, 2, 3, 4, 6, 43]
    Special cases:
          "all"    -> every refno in the full article list
          "last"   -> the most recently opened reference
          "latest" -> the most recently opened reference

    Used by cli_list().

    Returns:
        If successfully parsed, returns a list of reference numbers as
        integers.

    Raises:
        ArgumentError if the input was invalid in any way.
    """
    # Convert args into a string.
    # Because args should already have been split by spaces, we just need to
    # make sure that it's split by all commas.
    s = ','.join(args)
    strs = s.split(",")
    # The easy way out
    if strs == ["all"]:
        return set(range(1, len(_g.articleList) + 1))
    elif strs == ["last"] or strs == ["latest"]:
        # Get the index of the most recently opened article.
        # t is the (refno, article) tuple generated by enumerate(), and
        # t[1] is the article dictionary.
        argmax, _ = max(enumerate(_g.articleList, start=1),
                        key=lambda t: t[1].time_opened)
        return {argmax}
    # Otherwise we've got to parse it.
    refnos = set()   # to avoid duplicates
    try:
        for i in strs:
            if i == "":
                continue
            if "-" in i:
                # Parse the range.
                rmin, rmax = i.split("-")   # ValueError if too many entries
                rmin = int(rmin)
                rmax = int(rmax)
                if rmin >= rmax:
                    return _ret.FAILURE
                for m in range(rmin, rmax + 1):
                    refnos.add(m)
            else:
                refnos.add(int(i))          # ValueError if not castable to int
    except (ValueError, TypeError):
        # ValueError -- something couldn't be casted to int
        # TypeError  -- input wasn't iterable
        raise ArgumentError(f"invalid argument{_p(args)} {args}")

    # Basic argument checking
    for r in refnos:
        if r > len(_g.articleList):
            raise ArgumentError(f"no article with refno {r}")

    return list(refnos)


def parse_formats(args, abbrevs=None):
    """
    Parses command-line arguments as a series of formats.

    Arguments:
        args (list)    : Command-line arguments.
        abbrevs (dict) : Dictionary containing abbreviations for formats: the
                         keys are the long form and values are short form.

    Returns:
        List of formats in the form of one-letter codes.

    Raises:
        ArgumentError if the input was invalid.
    """
    s = "".join(args)
    # Handle long forms by converting them to their short forms
    if abbrevs is not None:
        for short, long in abbrevs.items():
            s = s.replace(long, short)
    # Pick out the alphabetical characters in the string
    t = set()
    try:
        for char in s:
            if char.isalpha():
                t.add(char)
    except (AttributeError, TypeError):
        # AttributeError -- isalpha() failed (i.e. not a character)
        # TypeError      -- input wasn't iterable
        raise ArgumentError(f"invalid argument{_p(args)} {args}")
    else:
        return list(t)


def parse_refnos_formats(args, abbrevs=None):
    """
    Parses command-line arguments as a combination of refnos and formats.

    Used by cli_open() and cli_cite().

    Arguments:
        args (list)    : Command-line arguments.
        abbrevs (dict) : Dictionary containing abbreviations for formats: the
                         keys are the long form and values are short form.
                         Passed directly to parse_formats().

    Returns:
        Tuple of (refnos, formats).

    Raises:
        ArgumentError if the input was invalid.
    """
    # Check for 'all' or 'last' -- this makes our job substantially easier
    # because it is the refno and everything else is the format
    if args[0] in ["all", "last", "latest"]:
        arg_refno = args[:1]
        arg_format = args[1:]
    # Otherwise we have to do it the proper way
    else:
        # Preprocess args
        argstr = ",".join(args)
        # The only allowable characters in refnos as [0-9,-], so we split the
        # full string accordingly by finding the first character in argstr that
        # isn't that.
        x = next((i for i, c in enumerate(argstr) if c not in "1234567890,-"),
                 len(argstr))
        arg_refno = argstr[:x].split(",")
        arg_format = argstr[x:].split(",")
    # Delegate to the individual functions.
    try:
        refnos = parse_refnos(arg_refno)
        formats = parse_formats(arg_format, abbrevs)
    except ArgumentError:
        # Catch the ArgumentError(s) in either one and raise one with the
        # original args.
        raise ArgumentError(f"invalid argument{_p(args)} {args}")
    else:
        return refnos, formats
