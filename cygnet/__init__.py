import sys

from .cygcls import DOI


def cite(doi, type="bib"):
    """
    This is a convenience function. Defaults to BibLaTeX citation style.
    """
    return DOI(doi).to_citation(type=type)


def cite_entrypoint():
    """
    Entry point for the `cygnet-cite` command which simply calls cite().
    """
    usage_str = ("usage: cygnet-cite DOI [TYPE]\n"
                 "available types: bib (default), doi, [Rr]st, [Ww]ord, [Mm]d")
    l = len(sys.argv)
    if l < 2:
        print("error: insufficient arguments", file=sys.stderr)
        print(usage_str, file=sys.stderr)
        sys.exit(2)
    if l == 2:
        try:
            s = cite(sys.argv[1])
        except ValueError as e:
            print("error: " + str(e), file=sys.stderr)
            print(usage_str, file=sys.stderr)
            sys.exit(1)
        else:
            print(s)
            sys.exit(0)
    elif l > 2:
        try:
            s = cite(sys.argv[1], type=sys.argv[2])
        except ValueError as e:
            print("error: " + str(e), file=sys.stderr)
            print(usage_str, file=sys.stderr)
            sys.exit(1)
        else:
            print(s)
            sys.exit(0)
