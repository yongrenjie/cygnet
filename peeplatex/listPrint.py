"""
This module provides tools for printing of lists and article information.
"""


import os

from ._shared import *
from .fmt import (fmtAuthor, fmtVolInfo, fmtJournalShort)


def printListHead(layout_str, fss):
    """
    Print the header.
    """
    # unpack field sizes
    number_fs, author_fs, year_fs, journal_fs, title_fs = fss
    # blank row
    print()
    # header row
    print(_g.ansiBold + layout_str.format("#", number_fs,
                                          "Authors", author_fs,
                                          "Year", year_fs,
                                          "Journal", journal_fs,
                                          "Title & DOI", title_fs) \
          + _g.ansiReset)
    # a horizontal line
    print("-" * (number_fs + author_fs + year_fs + journal_fs + title_fs))


def listOneArticle(i, a, layout_str, fss, printAvail=True):
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
    # get PDF availability if required
    if printAvail:
        pdfAvailStr = listPDFAvailability(a["doi"])
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
               printAvail and pdfAvailStr != "",
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
        # if PDF availability is desired, and the title and DOI have both been printed,
        # replace title with PDF availability
        if printAvail and a["title"] == "" and a["doi"] == "":
            a["title"] = pdfAvailStr
            printAvail = ""
        # print the next line of text
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
    # either use up the remaining space, or extend to the end of the longest title.
    # but make sure we use at least 10 columns
    total_columns = os.get_terminal_size().columns
    title_fs = min(total_columns - number_fs - author_fs - year_fs - journal_fs,
                   max(len(a["title"]) for a in arts))
    # Make it a reasonable size... OK it's because when you print ANSI escape
    # codes, you have to make sure that it's all on the same line, otherwise the
    # colour for the subsequent lines gets completely messed up. Now, the
    # listPDFAvailability() function returns a string that (including the ANSI
    # escape codes) is at most 37 characters. If we don't make title_fs at least
    # 37 characters long, then the colours will behave VERY weirdly. 40 is just
    # a nice round number near 37. And let's face it, do you really want to read
    # titles formatted in a field that is tiny?
    title_fs = max(40, title_fs)

    return (number_fs, author_fs, year_fs, journal_fs, title_fs)


def listPDFAvailability(doi):
    """
    Prints a green tick or a red cross indicating whether the PDF and/or SI
    are available for a given DOI.
    """
    formats = ["pdf", "si"]
    s = ""
    for f in formats:
        p = _g.currentPath.parent / f / (doi.replace('/','#') + ".pdf")
        if p.exists() and p.is_file():
            s += "{}\u2714{}{}".format(_g.ansiDiffGreen, _g.ansiReset, f)
        else:
            s += "{}\u2718{}{}".format(_g.ansiDiffRed, _g.ansiReset, f)
        s += "  "
    return s[:-2]  # remove the extra two spaces
