"""
This module provides tools for printing of lists and article information.
"""

import os

from _shared import _g


def printListHead(layout_str, fss):
    """
    Print the header.
    """
    # unpack field sizes
    number_fs, author_fs, year_fs, journal_fs, title_fs = fss
    # blank row
    print()
    # header row
    print(layout_str.format("#", number_fs,
                            "Authors", author_fs,
                            "Year", year_fs,
                            "Journal", journal_fs,
                            "Title & DOI", title_fs))
    # a horizontal line
    print("-" * (number_fs + author_fs + year_fs + journal_fs + title_fs))


def listOneArticle(i, a, layout_str, fss):
    """
    Print one article.
     i          - the number in front.
     a          - the article
     layout_str - the format string.
     fss        - tuple of field sizes: (number, author, year, journal, title)

    WARNING: This modifies the article in-place, so should only be called on copies!
    After this function is done, the info is completely unusable.
    """
    # unpack field sizes
    number_fs, author_fs, year_fs, journal_fs, title_fs = fss
    # generate volume info
    volinfo = fmtVolInfo(a)
    # print the first round of information
    first_author = a["authors"].pop(0)
    print(layout_str.format(i, number_fs,
                            fmtAuthor(first_author, style="display"), author_fs,
                            a["year"], year_fs,
                            fmtJournalShort(a["journalShort"]), journal_fs,
                            a["title"][:title_fs], title_fs))
    # cut off the first author
    a["title"] = a["title"][title_fs:]
    # if there is still information to be printed, print it
    while any([a["authors"] != [],
               a["title"] != "",
               a["doi"] != "",
               volinfo != ""]):
        # get an author if there is one
        try:
            next_author = a["authors"].pop(0)
        except IndexError:
            next_author = ""
        # replace the title with the DOI if the title has been printed and DOI hasn't
        if a["title"] == "" and a["doi"] != "":
            a["title"] = a["doi"]
            a["doi"] = ""
        print(layout_str.format("", number_fs,
                                fmtAuthor(next_author, style="display"), author_fs,
                                "", year_fs,
                                volinfo, journal_fs,
                                a["title"][:title_fs], title_fs))
        a["title"] = a["title"][title_fs:]
        volinfo = ""
    # empty line (for readability?)
    print()


def printDots(layout_str, fss):
    """
    Prints dots.
    """
    # unpack field sizes
    number_fs, author_fs, year_fs, journal_fs, title_fs = fss
    # header row
    print(layout_str.format("...", number_fs,
                            "...", author_fs,
                            "...", year_fs,
                            "...", journal_fs,
                            "...", title_fs))
    print()


def truncateAuthors(art, maxAuth):
    """
    Truncates the list of authors to a maximum of maxAuth lines.

    WARNING: This modifies the article in-place, so should only be called on copies!
    It removes any authors in the middle.
    """
    if maxAuth <= 0:
        return art
    else:
        l = len(art["authors"])
        if l > maxAuth:
            art["authors"] = [art["authors"][0],
                              art["authors"][1],
                              art["authors"][2],
                              {"family": "..."},
                              art["authors"][l - 1]]
        return art


def getFS(arts, refnos):
    """
    Calculates appropriate field sizes for the list output.
    Doesn't process arts or refnos -- just does it quite literally.
    """
    # Calculate field widths
    spaces = 2
    number_fs = max(len(str(r)) for r in refnos) + spaces
    author_fs = max(max(max(len(fmtAuthor(auth, style="display"))
                            for auth in art["authors"])
                        for art in arts),
                    len("Authors")
                    ) + spaces
    year_fs = 4 + spaces
    journal_fs = max(max(len(fmtJournalShort(art["journalShort"])) for art in arts),
                     max(len(fmtVolInfo(art)) for art in arts),
                     len("Journal info")
                     ) + spaces
    # either use up the remaining space, or extend to the end of the longest title
    total_columns = os.get_terminal_size().columns
    title_fs = min(total_columns - number_fs - author_fs - year_fs - journal_fs,
                   max(len(a["title"]) for a in arts))

    return (number_fs, author_fs, year_fs, journal_fs, title_fs)


def fmtAuthor(author, style=None):
    """
    Prettify author names.
    """
    # Return empty string for any Falsy value
    if not author:
        return ""
    # If there's no given name.
    # We should probably try to handle the no family name case, but
    #  I'm not sure when we will actually come across an example...
    if "given" not in author or author["given"] == []:
        return author["family"]
    # Standard case
    family_name = author["family"]
    given_names = author["given"]
    # Jonathan R. J. Yong -> JRJ Yong
    if style == "display":
        return "".join(n[0] for n in given_names.split()) + " " + author["family"]
    # Jonathan R. J. Yong -> Yong, J. R. J.
    elif style == "acs":
        return author["family"] + ", " + ". ".join(n[0] for n in given_names.split()) + "."
    # Jonathan R. J. Yong -> Yong, Jonathan R. J.
    elif style == "bib":
        # must remember to use control spaces.
        return (author["family"] + ", " + author["given"]).replace(". ", ".\\ ")
    # Otherwise just return the name as a string
    else:
        return given_names + " " + family_name


def fmtVolInfo(article):
    """
    Returns the string "vol (issue), page-page", or "vol, page-page" if
    no issue number is present.
    """
    if "issue" in article and article["issue"] != "":
        return "{} ({}), {}".format(article["volume"],
                                    article["issue"],
                                    article["pages"])
    else:
        return "{}, {}".format(article["volume"],
                               article["pages"])


def fmtJournalShort(jname):
    """
    Condenses the short journal name to something that's as readable as possible.

    This mainly works by stripping periods, but there are also some useful acronyms.
    """
    jname = jname.replace(".", "")
    for long, short in _g.jNameAbbrevs.items():
        jname = jname.replace(long, short)
    return jname
