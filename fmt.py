from _shared import *


"""
Module containing functions which format information nicely.
"""


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
    for longName, shortName in _g.jNameAbbrevs.items():
        jname = jname.replace(longName, shortName)
    return jname
