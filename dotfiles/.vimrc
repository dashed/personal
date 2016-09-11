"Alberto Leal's .vimrc file
"Contributions from many sources

set nocompatible
set background=dark

" remove trailing whitespace on save
autocmd BufWritePre * :%s/\s\+$//e

" wrap left/right
:set whichwrap+=>,l
:set whichwrap+=<,h

" When opening a new line and no filetype-specific indenting is enabled, keep
" the same indent as the line you're currently on. Useful for READMEs, etc.
"set autoindent
"set smartindent

"set tab character to 4 characters
set tabstop=4
set expandtab
set shiftwidth=4         " indent width for autoindent

" Use case insensitive search, except when using capital letters
set ignorecase
set smartcase

"Set color scheme
colorscheme desert
syntax enable

"Informative status line
set statusline=%F%m%r%h%w\ [TYPE=%Y\ %{&ff}]\ [%l/%L\ (%p%%)]

set number " Show line numbers
"set numberwidth=5 "Highlight current line
"set cursorline

set backspace=indent,eol,start " make backspace a more flexible

set ruler				" Show the line and column numbers of the cursor.
"set virtualedit=all		" freeroam cursor
set showmatch           " Show matching brackets.
set showmode            " Show current mode.

" Always display the status line, even if only one window is displayed
set laststatus=2

" Instead of failing a command because of unsaved changes, instead raise a
" dialogue asking if you wish to save changed files.
set confirm

" Enable use of the mouse for all modes
" set mouse=a

" REQUIRED. This makes vim invoke Latex-Suite when you open a tex file.
filetype plugin on

" IMPORTANT: grep will sometimes skip displaying the file name if you
" search in a singe file. This will confuse Latex-Suite. Set your grep
" program to always generate a file-name.
set grepprg=grep\ -nH\ $*

" OPTIONAL: This enables automatic indentation as you type.
filetype indent on

" OPTIONAL: Starting with Vim 7, the filetype of empty .tex files defaults to
" 'plaintex' instead of 'tex', which results in vim-latex not being loaded.
" The following changes the default filetype back to 'tex':
let g:tex_flavor='latex'

let g:Tex_ViewRule_pdf = 'Preview'
