"""
prompt.py
---------

Class that controls the main REPL.
"""

import asyncio
import re
from pathlib import Path

import prompt_toolkit as pt

from . import commands
from ._shared import *


class peepPrompt():
    """
    Interactive prompt.
    """

    style = pt.styles.Style.from_dict({
        "path" : f"{_g.ptPurple}",
        "peep" : f"{_g.ptPink} bold italic",
        ""     : _g.ptGreen,
    })
    def make_message(self):
        # Construct nice form of _g.currentPath..
        path = str(_g.currentPath) if _g.currentPath is not None else ""
        path = path.replace(str(Path.home()), "~")
        path = f"({path}) " if path else ""
        msg = [("class:path"  , path),
               ("class:peep", "peep > ")]
        return msg

    commentSymbol = '#'
    session = pt.PromptSession()

    intro = (
        f"\n{_g.ansiHelpYellow}"
        "/----------------------------------------------------------------\\\n"
        f"| {_g.ansiBold}PeepLaTeX v{_g.versionNo:<13s}{_g.ansiReset}{_g.ansiHelpYellow}                                       |\n"
        "| Available commands:                                            |\n"
        "| ----------------                                               |\n"
        "| r[ead] a file         w[rite] to a file                        |\n"
        "|                                                                |\n"
        "| l[ist] all articles   so[rt] articles     s[earch] in articles |\n"
        "|                                           ^^^^^^^^^^^^^^^^^^^^ |\n"
        "|                                              NOT IMPLEMENTED   |\n"
        "|                                                                |\n"
        "| a[dd] a DOI           d[elete] a ref      e[dit] a ref         |\n"
        "| c[ite] a ref          u[pdate] a ref                           |\n"
        "| i[mport] a new PDF                                             |\n"
        "|                                                                |\n"
        "| ap - add a PDF        dp - delete a PDF                        |\n"
        "| f[etch] a PDF (requires VPN)                                   |\n"
        "|                                                                |\n"
        "| un[do]                h <cmd> - help      q[uit]               |\n"
        f"\\----------------------------------------------------------------/{_g.ansiReset}\n"
    )

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

        # If any numbers are in the cmd, separate the bit with a number and
        # prepend it to args. This allows us to do things like "o1" or "c1d"
        # instead of "o 1" or "c 1d". Yes I'm lazy.
        # This one-liner is a bit obscure, but the alternative is a
        # full-fledged loop...
        n = next((i for i, c in enumerate(cmd) if c.isdigit()), len(cmd))
        if n < len(cmd):
            args = [cmd[n:]] + args
            cmd = cmd[:n]

        # Finally, check whether cmd is 'h' or 'help'
        help = cmd in ["h", "help"]
        if help:
            if args != []:
                # Strip the real command from the args
                cmd, args = args[0], args[1:]
            else:
                cmd, args = "", []
        return cmd, args, help

    async def loop(self):
        print(self.intro)
        with pt.patch_stdout.patch_stdout():
            while True:
                try:
                    line = await self.session.prompt_async(self.make_message(),
                                                           style=self.style)
                except KeyboardInterrupt:  # Ctrl-C
                    continue
                except EOFError:  # Ctrl-D
                    break
                else:
                    # Skip empty lines.
                    if line.strip() == "":
                        continue
                    # Otherwise, parse the line.
                    cmd, args, help = self.parseLine(line)

                    # Check for edge cases of help which cannot be delegated
                    # to the decorator.
                    if help and cmd == "":   # General help wanted
                        print(self.intro)
                        continue
                    elif help and cmd in ["q", "quit", "zzzpeep"]:
                        print(f"{_g.ansiHelpYellow}"
                              f"\n    Quits the programme.\n{_g.ansiReset}")
                        continue

                    # Run the desired command.
                    if cmd in ["q", "qu", "qui", "quit",             # QUIT
                               "zzzpeep"]:
                        break
                    elif cmd in ["c", "ci", "cit", "cite"]:          # CITE
                        asyncio.create_task(commands.cite(args, help=help))
                    elif cmd in ["o", "op", "ope", "open"]:          # OPEN
                        commands.openRef(args, help=help)
                    elif cmd in ["w", "wr", "wri", "writ",           # WRITE
                                 "write"]:
                        commands.cli_write(args, help=help)
                    elif cmd in ["l", "li", "ls", "lis", "list"]:    # LIST
                        commands.cli_list(args, help=help)
                    elif cmd in ["cd"]:                              # CD
                        commands.cli_cd(args, help=help)
                    elif cmd in ["e", "ed", "edi", "edit"]:          # EDIT
                        if help is False:
                            _saveHist(cmd, args)
                        commands.editRef(args, help=help)
                    elif cmd in ["a", "ad", "add"]:                  # ADD
                        if help is False:
                            _saveHist(cmd, args)
                        await commands.addRef(args, help=help)
                    elif cmd in ["d", "de", "del", "dele",           # DELETE
                                 "delet", "delete"]:
                        if help is False:
                            _saveHist(cmd, args)
                        await commands.deleteRef(args, help=help)
                    elif cmd in ["u", "up", "upd", "upda",           # UPDATE
                                 "updat", "update"]:
                        if help is False:
                            _saveHist(cmd, args)
                        await commands.updateRef(args, help=help)
                    elif cmd in ["s", "se", "search"]:               # SEARCH
                        _error("it's not been implemented yet...")
                    elif cmd in ["so", "sor", "sort"]:               # SORT
                        if help is False:
                            _saveHist(cmd, args)
                        commands.sortArticleList(args, help=help)
                    elif cmd in ["i", "im", "imp", "impo",           # IMPORT
                                 "impor", "import"]:
                        if help is False:
                            _saveHist(cmd, args)
                        await commands.importPDF(args, help=help)
                    elif cmd in ["ap", "addp", "addpd", "addpdf"]:   # ADDPDF
                        await commands.addPDF(args, help=help)
                    elif cmd in ["dp", "delp", "delpd", "delpdf",    # DELETEPDF
                                 "deletep", "deletepd", "deletepdf"]:
                        await commands.deletePDF(args, help=help)
                    elif cmd in ["f", "fe", "fet", "fetc",           # FETCH
                                 "fetch"]:
                        await commands.fetchPDF(args, help=help)
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
