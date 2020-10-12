from .cygcls import DOI


def cite(doi, type="bib"):
    """
    This is a convenience function. Defaults to BibLaTeX citation style.
    """
    return DOI(doi).to_citation(type=type)
