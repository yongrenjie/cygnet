"""
This module provides tools for list printing.
"""

import os


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
                            a["journal_short"].replace(".",""), journal_fs,
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


def getFS(l):
    """
    Calculates appropriate field sizes for the list output.

    I tried caching this information in the article entry, but it makes virtually zero
     difference to the runtime even for a library of 1400 articles, and it adds extra time
     for reading/writing from/to disk (for reading in 1400 articles, the time taken increased
     from ca 2.4 -> 2.7 seconds).
    It's also a mess, because that means you'd have to remember to cache the information every
     time you change the metadata.
    Unfortunately you also can't use functools.lru_cache with this, because in general it will
     expect a dictionary as the argument, which isn't hashable.
    """
    spaces = 2
    number_fs = len(str(len(l))) + spaces
    author_fs = max(max(max(len(fmtAuthor(auth, style="display")) for auth in art["authors"]) for art in l),
                    len("Authors")
                    ) + spaces
    year_fs = 4 + spaces
    journal_fs = max(max(len(art["journal_short"].replace(".","")) for art in l),
                     max(len(fmtVolInfo(art)) for art in l),
                     len("Journal info")
                     ) + spaces
    # either use up the remaining space, or extend to the end of the longest title
    total_columns = os.get_terminal_size().columns
    title_fs = min(total_columns - number_fs - author_fs - year_fs - journal_fs,
                   max(len(a["title"]) for a in l))

    return (number_fs, author_fs, year_fs, journal_fs, title_fs)


def fmtAuthor(author, style):
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
        return author["family"] + ", " + author["given"]
    # Otherwise just return the name as a string
    else:
        return given_names + " " + family_name


def fmtVolInfo(article):
    """
    Returns the string "vol (issue), page-page", or "vol, page-page" if
    no issue number is present.
    """
    if "issue" in article:
        return "{} ({}), {}".format(article["volume"],
                                    article["issue"],
                                    article["page"])
    else:
        return "{}, {}".format(article["volume"],
                               article["page"])
