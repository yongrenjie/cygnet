"""
This module contains helper functions which act on PDFs or DOIs.
"""


import re
import sys
import subprocess
import asyncio
from unicodedata import normalize
from pathlib import Path
from copy import deepcopy

import aiohttp
from unidecode import unidecode

from ._shared import *


def unicode2Latex(s):
    """
    Replaces Unicode characters in a string with their LaTeX equivalents.
    """
    for char in _g.unicodeLatexDict:
        s = s.replace(char, _g.unicodeLatexDict[char])
    return s


async def savePDF(path, doi, fmt):
    """
    Saves a PDF into the database itself.

    path should be a string. It can either be a Web page, or a path to a file.
    doi is the DOI.
    fmt is either 'pdf' or 'si'.
    """

    # first, boot out any silly ideas
    if '/' not in str(path):
        return _error("savePDF: invalid path '{}'".format(path))

    # This is crude, but should work as long as we only use absolute paths.
    type = "file" if str(path).startswith('/') else "url"

    # Construct the destination path (where the PDF should be saved to).
    pdest = _g.currentPath.parent / fmt / (doi.replace('/','#') + ".pdf")
    # mkdir -p the folder if it doesn't already exist.
    if not pdest.parent.exists():
        pdest.parent.mkdir(parents=True)

    if type == "file":
        # Process and check source path. Note that dragging-and-dropping
        # into the terminal gives us escaped spaces, hence the replace().
        psrc = str(path).replace("\\ "," ").strip()
        for escapedChar, char in _g.pathEscapes:
            psrc = psrc.replace(escapedChar, char)
        psrc = Path(psrc)
        if not psrc.is_file():
            return _error("savePDF: file {} not found".format(psrc))
        else:
            try:
                proc = subprocess.run(["cp", str(psrc), str(pdest)],
                                      check=True)
            except subprocess.CalledProcessError:
                return _error("savePDF: file {} could not be copied "
                              "to {}".format(psrc, pdest))
            else:
                return _ret.SUCCESS

    if type == "url":
        psrc = str(path).strip()
        try:
            async with _g.ahSession.get(psrc) as resp:
                # Handle bad HTTP status codes.
                if resp.status != 200:
                    return _error("savePDF: URL '{}' returned "
                                  "{} ({})".format(psrc, resp.status,
                                                   resp.reason))
                # Check if Elsevier is trying to redirect us.
                if "sciencedirect" in psrc and resp.content_type == "text/html":
                    # e = resp.get_encoding()
                    redirectRegex = re.compile(r"""window.location\s*=\s*'(https?://.+)';""")
                    text = await resp.text()
                    for line in text.split("\n"):
                        match = redirectRegex.search(line)
                        if match:
                            newurl = match.group(1)
                            _debug("Redirected by Elsevier, trying to fetch PDF from new URL")
                            newSave = asyncio.create_task(savePDF(newurl, doi, fmt))
                            await asyncio.wait([newSave])
                            return newSave.result()
                elif "wiley" in psrc and resp.content_type == "text/html":
                    text = await resp.text()
                    for line in text.split("\n"):
                        print(line)
                    return _error("screw wiley")
                # Otherwise, check if we are actually getting a PDF
                if "application/pdf" not in resp.content_type:
                    return _error("savePDF: URL '{}' returned content-type "
                                  "'{}'".format(psrc, resp.content_type))

                # OK, so by now we are pretty sure we have a working link to a
                # PDF. Try to get the file size.
                filesize = None
                try:
                    filesize = int(resp.headers["content-length"])
                except (KeyError, ValueError):
                    pass
                # Create spinner.
                if filesize is not None:
                    prog = _progress(filesize/(2**20), fstr="{:.2f}")  # in MB
                    spin = asyncio.create_task(_spinner("Downloading file", prog, "MB"))
                else:
                    spin = asyncio.create_task(_spinner("Downloading file"))

                # Stream the content.
                with open(pdest, 'wb') as fp:
                    chunkSize = 2048   # bytes
                    while True:  # good argument for assignment expression here
                        chunk = await resp.content.read(chunkSize)
                        if not chunk:
                            break
                        fp.write(chunk)
                        if filesize is not None:
                            prog.incr(chunkSize/(2**20))
                # Cancel spinner
                spin.cancel()
                await asyncio.sleep(0)

        # lookup failed
        except (aiohttp.client_exceptions.ContentTypeError,
                aiohttp.client_exceptions.InvalidURL,
                aiohttp.client_exceptions.ClientConnectorError):
            return _error("savePDF: URL '{}' not accessible".format(psrc))
        else:
            return _ret.SUCCESS
