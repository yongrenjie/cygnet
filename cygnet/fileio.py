"""
fileio.py
---------

Functions involving reading / writing to a file.
"""

from pathlib import Path

import yaml

from .cygcls import Article


def read_articles(fname):
    """
    Read a list of articles from the specified directory.

    Arguments:
        path (Path) : Path to read from.

    Raises:
        FileNotFoundError: If the file does not exist.
        yaml.YAMLError   : If the file is not valid YAML, or it isn't in the
                           appropriate format for Cygnet.
    """
    if not fname.is_file():
        raise FileNotFoundError(f"The file {fname} does not exist.")

    # Read it in
    with open(fname, "r") as fp:
        article_dicts = list(yaml.safe_load_all(fp))

    # Convert to Article instances. This implicitly validates the data.
    try:
        articles = [Article(**d) for d in article_dicts]
    except TypeError:
        raise yaml.YAMLError(f"The file {fname} did not contain "
                             "articles in the correct format.")

    return articles


def write_articles(articles, fname, force=False):
    """
    Serialises a list of articles into the specified directory and file.

    Arguments:
        articles (list): List of articles. Each item should be a dictionary.
        dir (Path)     : Directory to save to.
        fname (str)    : Filename to write to.
        force (bool)   : Whether to create the directory if it doesn't exist.

    Returns:
        None.

    Raises:
        FileNotFoundError: If dir does not exist and force is False.
    """
    # Check if parent directory exists. If not, then make it if force is True.
    if not fname.parent.is_dir():
        if force:
            fname.parent.mkdir(parents=True)
        else:
            raise FileNotFoundError(f"The directory {fname.parent} "
                                    "does not exist.")

    # Serialise the articles as dictionaries.
    article_dicts = [vars(article) for article in articles]
    with open(fname, "w") as fp:
        yaml.dump_all(article_dicts, fp)
