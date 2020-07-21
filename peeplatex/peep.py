import os
import sys
import asyncio
import argparse
import re
from pathlib import Path
from enum import Enum
from datetime import datetime, timezone
from operator import attrgetter

import yaml
import aiohttp
import prompt_toolkit as pt

from . import refMgmt
from . import listPrint
from .commands import *
from ._shared import *


class peepPrompt():
    """
    Interactive prompt.
    """

    style = pt.styles.Style.from_dict({
        "path" : "{}".format(_g.ptPurple),
        "peep" : "{} bold italic".format(_g.ptPink),
        ""     : _g.ptGreen,
    })
    def make_message(self):
        # Construct nice form of _g.currentPath..
        path = str(_g.currentPath.parent) if _g.currentPath is not None else ""
        path = path.replace(str(Path.home()), "~")
        path = "({}) ".format(path) if path else ""
        msg = [("class:path"  , path),
               ("class:peep", "peep > ")]
        return msg

    commentSymbol = '#'
    session = pt.PromptSession()

    intro = "\n" + "{}".format(_g.ansiHelpYellow) + \
        "/----------------------------------------------------------------\\" + "\n" + \
        "| {}PeepLaTeX v{:<13s}{}{}                                       |".format(_g.ansiBold,
                                                                                    _g.versionNo,
                                                                                    _g.ansiReset,
                                                                                    _g.ansiHelpYellow) + "\n" + \
        "| Available commands:                                            |" + "\n" + \
        "| ----------------                                               |" + "\n" + \
        "| r[ead] a file         w[rite] to a file                        |" + "\n" + \
        "|                                                                |" + "\n" + \
        "| l[ist] all articles   so[rt] articles     s[earch] in articles |" + "\n" + \
        "|                                           ^^^^^^^^^^^^^^^^^^^^ |" + "\n" + \
        "|                                              NOT IMPLEMENTED   |" + "\n" + \
        "|                                                                |" + "\n" + \
        "| a[dd] a DOI           d[elete] a ref      e[dit] a ref         |" + "\n" + \
        "| c[ite] a ref          u[pdate] a ref                           |" + "\n" + \
        "| i[mport] a new PDF                                             |" + "\n" + \
        "|                                                                |" + "\n" + \
        "| ap - add a PDF        dp - delete a PDF                        |" + "\n" + \
        "| f[etch] a PDF (requires VPN)                                   |" + "\n" + \
        "|                                                                |" + "\n" + \
        "| un[do]                h <cmd> - help      q[uit]               |" + "\n" + \
        "\\----------------------------------------------------------------/" + "{}".format(_g.ansiReset) + "\n"

    def parseLine(self, line):
        """
        Parses the command-line input.
        """
        # Remove anything after a comment
        if self.commentSymbol in line:
            line = line.split(self.commentSymbol)[0].rstrip()
        # We need to split at spaces, but not at escaped spaces, e.g.
        # in file names.
        line = re.split(r'(?<!\\) ', line)
        # Then replace the escaped spaces with ordinary spaces. We
        # assume here that there is no other legitimate uses for
        # escaped spaces, apart from file names.
        line = [l.replace("\\ ", " ") for l in line]
        # Replace other escaped characters.
        for escapedChar, char in _g.pathEscapes:
            line = [l.replace(escapedChar, char) for l in line]
        # Separate into command + arguments.
        cmd, args = line[0], line[1:]
        # Remove empty arguments.
        args = [a for a in args if a]
        # I have typed in :q more than once
        cmd = cmd.lstrip(":")
        # Return
        return cmd, args

    async def loop(self):
        print(self.intro)
        with pt.patch_stdout.patch_stdout():
            while True:
                try:
                    line = await self.session.prompt_async(self.make_message(),
                                                           style=self.style)
                except KeyboardInterrupt:
                    continue
                except EOFError:
                    break
                else:
                    # Skip empty lines.
                    if line.strip() == "":
                        continue
                    # Otherwise, parse the line.
                    cmd, args = self.parseLine(line)

                    # Look for help command. If so, remove help from the command,
                    # and delegate to the actual command which will print its
                    # own docstring. (See _helpdeco.)
                    help = False
                    if cmd in ["h", "help"]:
                        if args == []:   # general help wanted
                            print(self.intro)
                            continue
                        else:
                            help = True
                            cmd = args[0]
                            args = args[1:]
                            # 'q' doesn't delegate to a routine, so we need to
                            # catch it here.
                            if cmd in ["q", "quit", "zzzpeep"]:
                                print("{}{}{}".format(_g.ansiHelpYellow,
                                                      "\n    Quits the programme.\n",
                                                      _g.ansiReset))
                                continue

                    # If any numbers are in the cmd, separate the bit with 
                    # a number and prepend it to args. This allows us to do
                    # things like "o1" instead of "o 1". Yes I'm lazy.
                    n = next((i for i, c in enumerate(cmd) if c.isdigit()), len(cmd))
                    if n < len(cmd):
                        args = [cmd[n:]] + args
                        cmd = cmd[:n]

                    if cmd in ["q", "qu", "qui", "quit",             # QUIT
                               "zzzpeep"]:
                        break
                    elif cmd in ["c", "ci", "cit", "cite"]:          # CITE
                        asyncio.create_task(cite(args, help=help))
                    elif cmd in ["o", "op", "ope", "open"]:          # OPEN
                        openRef(args, help=help)
                    elif cmd in ["w", "wr", "wri", "writ",           # WRITE
                                 "write"]:
                        write(args, help=help)
                    elif cmd in ["l", "li", "ls", "lis", "list"]:    # LIST
                        listArticles(args, help=help)
                    elif cmd in ["r", "re", "rea", "read"]:          # READ
                        read(args, help=help)
                    elif cmd in ["e", "ed", "edi", "edit"]:          # EDIT
                        if help is False:
                            _saveHist(cmd, args)
                        editRef(args, help=help)
                    elif cmd in ["a", "ad", "add"]:                  # ADD
                        if help is False:
                            _saveHist(cmd, args)
                        await addRef(args, help=help)
                    elif cmd in ["d", "de", "del", "dele",           # DELETE
                                 "delet", "delete"]:
                        if help is False:
                            _saveHist(cmd, args)
                        await deleteRef(args, help=help)
                    elif cmd in ["u", "up", "upd", "upda",           # UPDATE
                                 "updat", "update"]:
                        if help is False:
                            _saveHist(cmd, args)
                        await updateRef(args, help=help)
                    elif cmd in ["s", "se", "search"]:               # SEARCH
                        _error("it's not been implemented yet...")
                    elif cmd in ["so", "sor", "sort"]:               # SORT
                        if help is False:
                            _saveHist(cmd, args)
                        sortArticleList(args, help=help)
                    elif cmd in ["i", "im", "imp", "impo",           # IMPORT
                                 "impor", "import"]:
                        if help is False:
                            _saveHist(cmd, args)
                        await importPDF(args, help=help)
                    elif cmd in ["ap", "addp", "addpd", "addpdf"]:   # ADDPDF
                        await addPDF(args, help=help)
                    elif cmd in ["dp", "delp", "delpd", "delpdf",    # DELETEPDF
                                 "deletep", "deletepd", "deletepdf"]:
                        await deletePDF(args, help=help)
                    elif cmd in ["f", "fe", "fet", "fetc",           # FETCH
                                 "fetch"]:
                        await fetchPDF(args, help=help)
                    elif cmd in ["un", "und", "undo"]:               # UNDO
                        _undo(help=help)
                    elif cmd in ["exec"] and _g.debug:               # EXEC
                        import traceback
                        # Execute arbitrary code. Useful for inspecting internal state.
                        try:
                            exec("_res =  " + " ".join(args), globals(), locals())
                            print(locals()["_res"])
                        except Exception as e:
                            traceback.print_exc()
                    elif cmd in ["pee"]:                             # PEE
                        print("zzzpee...")
                    elif cmd in ["peep", "PEEP"]:                    # PEEP
                        print("PEEP!")
                    else:                                            # unknown
                        _error("command '{}' not recognised".format(cmd))

                    # Need a tiny sleep to paper over a weird bug.
                    # Try removing this and spamming 'l' before quitting
                    #  to see the bug.
                    # There WILL be bugs if the time taken to print any
                    #  output (e.g. 'l' with large databases) exceeds
                    #  this sleep. With 3 references, printing takes a
                    #  fraction of a millisecond. With 300 references
                    #  it takes about 60 ms.
                    await asyncio.sleep(0.1)   # 100 ms.
        return


async def _autosave():
    """
    Checks every _g.autosaveInterval seconds for changes. If changes have been
    made, saves _g.articleList to _g.currentPath.
    """
    while True:
        try:
            await asyncio.sleep(_g.autosaveInterval)
            # Right now we only have one article list at a time, and
            #  changes just contains sentinel values.
            l = len(_g.changes)
            if _g.articleList and _g.currentPath and l != 0:
                _debug("autosave: found {} change{}: {}".format(l,
                                                                _p(l),
                                                                " ".join(_g.changes)))
                write(silent=True)
                _debug("autosave complete")
                _g.changes = []
        except asyncio.CancelledError:
            break


def backup():
    """
    Saves _g.articleList (if it isn't empty) to the backups folder.
    """
    if _g.maxBackups == 0:
        return
    if _g.articleList != [] and _g.currentPath is not None:
        dbName = _g.currentPath.name
        # Figure out the folder name
        backupFolder = _g.currentPath.parent / "backups"
        if not backupFolder.exists():
            backupFolder.mkdir()
        # Clean up the folder if it's too cluttered
        # This sorts in descending order of time created
        oldBackups = sorted([i for i in backupFolder.iterdir()
                             if i.name.startswith(dbName)],
                            key=attrgetter('name'),
                            reverse=True)
        # Deletes anything after the _g.maxBackups - 1 newest ones
        #  (because after we back up, there will be _g.maxBackups
        #  backups).
        if len(oldBackups) >= _g.maxBackups:
            for oldBackup in oldBackups[_g.maxBackups - 1:]:
                _debug("backup: deleting old backup {}".format(oldBackup))
                oldBackup.unlink()
        # Do the backup
        now = datetime.now().strftime(".%y%m%d_%H%M%S")
        fname = backupFolder / (dbName + now)
        write(fname, silent=True)
        _debug("backup: completed")
    else:
        _debug("backup: failed to back up articleList "
               "(length {}) with currentPath '{}'".format(len(_g.articleList),
                                                          _g.currentPath))


async def main_coro():
    """
    Main coroutine.
    """
    # Start autosave task
    t_autosave = asyncio.create_task(_autosave())

    # Launch aiohttp session with nice user-agent default header.
    async with aiohttp.ClientSession(connector=_g.ahConnector,
                                     headers=_g.httpHeaders) as ahSession:
        # ahSession only exists in this context manager block, so to avoid
        # having to pass it 1 million times through subroutines, we bind it
        # to a global variable first
        _g.ahSession = ahSession
        # Start the REPL
        pmt = peepPrompt()
        pmtloop = await pmt.loop()

    # Shutdown code
    print("Exiting... zzzpeep")
    # Stop autosave
    t_autosave.cancel()
    # prompt_toolkit bug if you spam commands like crazy
    count = 0
    for t in asyncio.all_tasks():
        if "wait_for_timeout()" in repr(t):
            count += 1
            t.cancel()
    _debug("{} timeout tasks cancelled.".format(count))


def main():
    """
    Run the main coroutine.
    """
    # Resize terminal
    cols, rows = os.get_terminal_size()
    cols = max(cols, 175)
    rows = max(rows, 50)
    sys.stdout.write(f"\x1b[8;{rows};{cols}t")

    # Parse sys.argv
    parser = argparse.ArgumentParser()
    parser.add_argument("db", help="YAML file to load upon startup",
                        nargs='?')
    # In the future we will change this to --debug, but I want all the
    # debugging stuff while this is still in development.
    parser.add_argument("--nodebug", help="Disable debugging output",
                        action="store_true")
    args = parser.parse_args()
    _g.debug = not args.nodebug
    if _g.debug:
        _debug("Debugging mode enabled.")

    # Read in the file specified in argv. This automatically performs a backup.
    infile = Path(args.db).resolve().expanduser() if args.db else Path.cwd()
    if infile.exists() and infile.is_dir():
        infile = infile / "db.yaml"
    if infile.exists() and infile.is_file():
        read(infile)

    # Run main coroutine until complete
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main_coro())
    loop.close()


if __name__ == "__main__":
    main()
