# peeplatex

An extremely minimalistic reference manager written in Python 3.

Package dependencies:
 - `aiohttp`
 - `prompt_toolkit`
 - `pyyaml`
 - `unidecode`

## Function for autoexpanding DOIs in Vim

After installing `peeplatex` citations can be generated (in Python) using

```python
from peeplatex.peepcls import DOI
DOI(doi).to_citation(type="bib")
```

where `doi` is the DOI of the article given as a string. (Try it in a REPL!)

A short Vimscript function (and key mapping) that leverages this functionality is as follows.
There is some code to ensure that each article is always surrounded by one line of whitespace (a largely cosmetic option).

```vim
function ExpandDOI()
let doi = expand("<cWORD>")
echo "expanding DOI " .. doi .. "..."
python3<<EOF
import vim
from peeplatex.peepcls import DOI
# get the citation
doi = vim.eval('expand("<cWORD>")')
try:
    citation = DOI(doi).to_citation(type="bib")
except Exception as e:
    citation = "error"
vim.command("let citation='{}'".format(citation))
EOF
if citation != "error"
    " twiddle with empty lines before citation
    let lineno = line(".")
    if lineno != 1
        let prevline = getline(lineno - 1)
        if !empty(trim(prevline))
            let x = append(lineno - 1, "")
        endif
    endif
    " delete the line with the citation
    delete _
    " put the citation
    put! =citation | redraw
    " twiddle with empty lines after citation
    if !empty(trim(getline(line(".") + 1)))
        let x = append(line("."), "")
        redraw
    endif
else
    redraw | echohl ErrorMsg | echo "invalid DOI " .. doi | echohl None
endif
endfunction

nnoremap <leader>e :call ExpandDOI() <CR>
```

This can be placed inside, for example, `~/.vim/ftplugin/bib.vim`.
After that, pressing `<leader>e` when the cursor is over a DOI should automatically expand it into a full Bib(La)TeX reference.
Note that the line containing the DOI will be deleted, so it should be placed on a line of its own!
