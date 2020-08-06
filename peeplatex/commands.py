"""
commands.py
-----------

Functions which the command line calls. These should NOT be used by other
functions in the programme, as the interface is designed SOLELY for command
line usage!
"""

import subprocess
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
from . import peeparticle
from . import refMgmt
from . import backup
from . import peepspin
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
    to read in a database from a db.yaml file.

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
        fileio.write_articles(_g.articleList, _g.currentPath / "db.yaml")

    # Change the path
    _g.previousPath, _g.currentPath = _g.currentPath, p

    # Try to read in the yaml file, if it exists
    try:
        new_articles = fileio.read_articles(p / "db.yaml")
    except yaml.YAMLError:
        _error(f"cd: A db.yaml file was found in {p}, "
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
        fileio.write_articles(_g.articleList, _g.currentPath / "db.yaml")
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
        'markdown' or 'm'      - Markdown form of 'short' ACS style citation.
        'Markdown' or 'M'      - Markdown form of 'long' ACS style citation.
        'doi' or 'd'           - Just the DOI.
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
                   f"        Use 'u[pdate] {refno}' to refresh metadata.")
            no += 1
        else:
            dois.append(doi)
    if dois == []:
        return

    articles = []
    coroutines = [peeparticle.doi_to_article_cr(doi, _g.ahSession)
                  for doi in dois]
    async with peepspin.Spinner(message="Fetching metadata...",
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
            peeparticle.diff_articles(peeparticle.Article(), article)
            msg = "add: accept new data (y/n)? ".format()
            style = pt.styles.Style.from_dict({"prompt": _g.ptBlue, "": _g.ptGreen})
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
    crts = [peeparticle.doi_to_article_cr(article.doi, _g.ahSession)
            for article in old_articles]
    new_articles = []
    # Perform asynchronous HTTP requests
    async with peepspin.Spinner(message="Fetching metadata...",
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
        ndiffs = peeparticle.diff_articles(old_article, new_article)
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
                if pdf.is_file():
                    pdf.unlink()
            # Then delete the article
            del _g.articleList[refno - 1]
            yes += 1
        print(f"delete: {yes} ref{_p(yes)} deleted")
        _g.changes += ["delete"] * yes
    else:
        print("delete: no refs deleted")
    return _ret.SUCCESS


# TODO halfway refactoring cli_import.

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

    ** Function details **
    This is only meant to be invoked from the command-line.

    Arguments:
        args: List of command-line options.

    Returns:
        Tuple (yes, no) containing number of PDFs successfully added and
        number of PDFs that were not added.
    """
    # Argument processing
    if args == []:
        return _error("import: no path(s) provided")

    # Get paths from the args.
    paths = parse_path(args)
    # Find directories and get files from them
    dirs = [p for p in paths if p.is_dir()]
    files = [p for p in paths if p.is_file()]
    for dir in dirs:
        files += [f for f in dir.iterdir() if f.suffix == ".pdf"]

    yes, no = 0, 0
    # Process every PDF file found.
    for file in files:
        # Try to get the DOI
        doi = refMgmt.PDFToDOI(file)
        if doi == _ret.FAILURE:
            no += 1
        else:
            print(f"import: detected DOI {doi} for PDF '{file}'")
            # Check whether it's already in the database
            for refno, article in enumerate(_g.articleList, start=1):
                if doi == article.doi:
                    _error(f"import: DOI {doi} already in database. Use "
                           f"'ap {refno}' to associate this PDF with it.")
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
                    await refMgmt.savePDF(file, doi, "pdf")
    # Trigger autosave
    _g.changes += ["import"] * yes
    return yes, no


@_helpdeco
async def addPDF(args):
    """
    Usage: addpdf (or ap) refno[...]

    Add a PDF to an existing reference in the database. Arguments can be
    provided as refnos. See 'h list' for more details on the syntax. This
    function will then prompt you for a link to the file; this can be provided
    as either a URL or an (absolute) file system path. File paths can be most
    easily provided by dragging-and-dropping a file into the terminal window.

    Note that PDFs that have already been saved cannot be changed using this
    command. You have to delete the PDF first (using 'dp'), then re-add the
    new PDF.

    ** Function details **
    This is meant to be only invoked from the command-line.

    Arguments:
        args: List of command-line arguments.

    Returns: TBD.
    """
    if _g.articleList == []:
        return _error("addPDF: no articles have been loaded")
    if args == []:
        return _error("addPDF: no references selected")

    # no formats to process; just refnos
    refnos = refMgmt.parseRefno(",".join(args))
    # Check the returned values
    ls = len(_g.articleList)
    if refnos is _ret.FAILURE or refnos == [] or any(r > ls for r in refnos):
        return _error("addPDF: invalid argument{} '{}' given".format(_p(args),
                                                                     " ".join(args)))

    formats = ["pdf", "si"]
    yes, no = 0, 0
    # We wrap the whole thing in try/except to catch Ctrl-C, which will get us
    # out of the entire loop quickly. Sending Ctrl-D just moves us to the next
    # refno.
    try:
        for i, r in enumerate(refnos):
            # Print the title.
            doi = _g.articleList[r - 1]["doi"]
            title = _g.articleList[r - 1]["title"]
            year = _g.articleList[r - 1]["year"]
            author = _g.articleList[r - 1]["authors"][0]["family"]
            if i != 0:
                print()  # Just a bit easier to read.
            print("{}({}) {} {}:{} {}".format(_g.ansiBold, r, author, year,
                                               _g.ansiReset, title))

            # Check whether the PDFs are already available.
            avail = {}  # mapping of format -> Bool
            for f in formats:
                p = _g.currentPath.parent / f / (doi.replace('/','#') + ".pdf")
                if p.exists() and p.is_file():
                    print(" {}\u2714{} {}   ".format(_g.ansiDiffGreen, _g.ansiReset, f))
                    avail[f] = True
                else:
                    print(" {}\u2718{} {}   ".format(_g.ansiDiffRed, _g.ansiReset, f))
                    avail[f] = False

            style = pt.styles.Style.from_dict({"prompt": _g.ptBlue, "": _g.ptGreen})
            msg = {"pdf": "addPDF: provide path to PDF (leave empty to skip): ",
                   "si": "addPDF: provide path to SI (leave empty to skip): "}
            # If both are available
            if avail["pdf"] and avail["si"]:
                print("Both PDF and SI found.")
                continue
            # At least one isn't available
            else:
                for f in (fmt for fmt in avail.keys() if not avail[fmt]):
                    try:
                        ans = await pt.PromptSession().prompt_async(msg[f],
                                                                    style=style)
                    except EOFError:  # move on to next question...
                        continue
                    if ans.strip():
                        saveTask = asyncio.create_task(refMgmt.savePDF(ans, doi, f))
                        await asyncio.wait([saveTask])
                        if saveTask.result() == _ret.FAILURE:
                            no += 1
                        else:
                            yes += 1
    except KeyboardInterrupt:
        pass

    print("addPDF: {} PDFs added, {} failed".format(yes, no))
    return _ret.SUCCESS


@_helpdeco
async def deletePDF(args, silent=False):
    """
    Usage: deletepdf (or dp) refno[...]

    Deletes PDF files associated with one or more references.

    At least one refno must be specified. For more details about how to specify
    refnos, type 'h list'.

    ** Function details **
    Deletes PDFs.

    Arguments:
        args  : List of command-line arguments.
        silent: If False, prompts the user for confirmation before deleting.

    Returns:
        Return values as described in _ret.
    """
    if _g.articleList == []:
        return _error("deletePDF: no articles have been loaded")
    if args == []:
        return _error("deletePDF: no references selected")

    # no formats to process; just refnos
    refnos = refMgmt.parseRefno(",".join(args))
    # Check the returned values
    ls = len(_g.articleList)
    if refnos is _ret.FAILURE or refnos == [] or any(r > ls for r in refnos):
        return _error("deletePDF: invalid argument{} '{}' given".format(_p(args),
                                                                        " ".join(args)))

    yes = 0
    for i, r in enumerate(refnos):
        # Print the title.
        doi = _g.articleList[r - 1]["doi"]
        title = _g.articleList[r - 1]["title"]
        year = _g.articleList[r - 1]["year"]
        author = _g.articleList[r - 1]["authors"][0]["family"]
        if not silent:
            if i != 0:
                print()  # Just a bit easier to read.
            print("{}({}) {} {}:{} {}".format(_g.ansiBold, r, author, year,
                                               _g.ansiReset, title))
        # Check whether the PDFs are actually available.
        avail = {}  # mapping of format -> Bool
        for f in ["pdf", "si"]:
            p = _g.currentPath.parent / f / (doi.replace('/','#') + ".pdf")
            if p.exists() and p.is_file():
                avail[f] = True
                if not silent:
                    print(" {}\u2714{} {}   ".format(_g.ansiDiffGreen, _g.ansiReset, f))
            else:
                avail[f] = False
                if not silent:
                    print(" {}\u2718{} {}   ".format(_g.ansiDiffRed, _g.ansiReset, f))

        # If both are not available
        if not avail["pdf"] and not avail["si"]:
            print("No PDFs associated with reference {} found.".format(r))
            continue
        # At least one available. Prompt user for format to delete
        else:
            if not silent:
                style = pt.styles.Style.from_dict({"prompt": "{} bold".format(_g.ptBlue),
                                                   "": _g.ptGreen})
                msg = "deletePDF: Confirm deletion by typing formats to be deleted: "
                try:
                    ans = await pt.PromptSession().prompt_async(msg)
                except (KeyboardInterrupt, EOFError):
                    continue  # to the next refno
                # Parse user input and delete files as necessary
                else:
                    ans = ans.replace("pdf", "p").replace("si", "s")
                    fs = refMgmt.parseFormat(ans)
                    if fs == _ret.FAILURE or any(f not in ['p', 's'] for f in fs) \
                            or ('p' in fs and not avail["pdf"]) \
                            or ('s' in fs and not avail["si"]):
                        _error("deletePDF: invalid response, no PDFs deleted")
                        continue  # to the next refno
            else:
                # Didn't want to be prompted. Just delete everything without
                # any error checking.
                fs = ['p', 's']

            # If we reached here, that means we should delete files.
            if 'p' in fs:
                path = _g.currentPath.parent / "pdf" / \
                    (doi.replace('/','#') + ".pdf")
                try:
                    subprocess.run(["rm", str(path)],
                                   stderr=subprocess.DEVNULL,
                                   check=True)
                except subprocess.CalledProcessError:  # file not found
                    pass
                else:
                    yes += 1
            if 's' in fs:
                path = _g.currentPath.parent / "si" / \
                    (doi.replace('/','#') + ".pdf")
                try:
                    subprocess.run(["rm", str(path)],
                                   stderr=subprocess.DEVNULL,
                                   check=True)
                except subprocess.CalledProcessError:  # file not found
                    pass
                else:
                    yes += 1

    print("deletePDF: {} PDFs deleted".format(yes))
    return _ret.SUCCESS


@_helpdeco
async def fetchPDF(args):
    """
    Usage: f[etch] refno[...]

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
    if _g.articleList == []:
        return _error("fetchPDF: no articles have been loaded")
    if args == []:
        return _error("fetchPDF: no references selected")

    # no formats to process; just refnos
    refnos = refMgmt.parseRefno(",".join(args))
    # Check the returned values
    ls = len(_g.articleList)
    if refnos is _ret.FAILURE or refnos == [] or any(r > ls for r in refnos):
        return _error("fetchPDF: invalid argument{} '{}' given".format(_p(args),
                                                                       " ".join(args)))

    # Check which ones need downloading
    dois = []
    for r in refnos:
        doi = _g.articleList[r - 1]["doi"]
        p = _g.currentPath.parent / "pdf" / (doi.replace('/','#') + ".pdf")
        if not (p.exists() and p.is_file()):
            dois.append(doi)
        else:
            print("fetchPDF: PDf for ref {} already in library".format(r))

    yes, no = 0, 0
    # Start the downloads!
    if len(dois) > 0:
        prog = _progress(len(dois))
        spin = asyncio.create_task(_spinner("Obtaining URLs", prog))
        results = []

        # Each coroutine returns a 2-tuple; the first component is
        # the doi, and the second is the URL if it didn't fail (or
        # a _ret.FAILURE if it did).
        coros = [refMgmt.DOIToFullPDFURL(doi, _g.ahSession) for doi in dois]
        for coro in asyncio.as_completed(coros):
            results.append(await coro)
            prog.incr()
        spin.cancel()
        await asyncio.sleep(0)

        for result in results:
            if result[1] == _ret.FAILURE:
                no += 1
            else:
                x = await refMgmt.savePDF(result[1], result[0], "pdf")
                if x == _ret.FAILURE:
                    no += 1
                else:
                    yes += 1

    print("fetchPDF: {} PDFs successfully fetched, {} failed".format(yes, no))
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
    for path in paths:
        if not path.is_absolute():
            path = _g.currentPath / path
        path = path.resolve().expanduser()
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
