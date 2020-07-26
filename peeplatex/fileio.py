"""
fileio.py
---------

Functions involving reading / writing to a file.
"""

import yaml

from .peeparticle import Article


def read_articles(dir, fname="db.yaml"):
    """
    Read a list of articles from the specified directory.

    Arguments:
        dir (Path) : Directory to read from.
        fname (str): Filename to read.

    Raises:
        FileNotFoundError: If the file does not exist.
        yaml.YAMLError   : If the file doesn't contain articles in the correct
                           format.
    """
    if not (dir / fname).is_file():
        raise FileNotFoundError(f"The file {dir / fname} does not exist.")

    # Read it in
    with open(dir / fname, "r") as fp:
        article_dicts = list(yaml.safe_load_all(fp))

    # Convert to Article instances. This implicitly validates the data.
    articles = [Article(**d) for d in article_dicts]

    return articles


def write_articles(articles, dir, fname="db.yaml", force=False):
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
    # Check if directory exists. If not, then make it if force is True.
    if not dir.is_dir():
        if force:
            dir.mkdir(parents=True)
        else:
            raise FileNotFoundError(f"The directory {dir} does not exist.")

    # Serialise list of articles.
    article_dicts = [vars(article) for article in articles]
    with open(dir / fname, "w") as fp:
        yaml.dump_all(article_dicts, fp)
