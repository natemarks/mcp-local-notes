# Research: Idiomatic file-type detection and opening on Ubuntu 26.04

Issue: [#51 Idiomatic file-type detection and opening on Ubuntu 26.04](https://github.com/natemarks/mcp-local-notes/issues/51)
(child of map issue [#48](https://github.com/natemarks/mcp-local-notes/issues/48))

Question: on Ubuntu 26.04, what is the idiomatic way to (a) identify a file's
type and (b) open a non-text file with the user's default app? The comparison
covers `file`/libmagic, shared-mime-info (`xdg-mime`), and GIO (`gio info`,
`gio open`) against `xdg-open`. It also covers txt/md reliability, the MIME
inheritance tree as a basis for an "editable in nvim" rule, how fast `scan` can
run over thousands of files, and how to launch the opener detached from nvim.

**Test machine** (all the empirical results below come from it): Ubuntu 26.04.1,
GNOME session (`XDG_CURRENT_DESKTOP=ubuntu:GNOME`), `file` 5.46
(`1:5.46-5build2`), `shared-mime-info` 2.4, `xdg-utils` 1.2.1, `libglib2.0-bin`
2.88.0, Go 1.26.8, Neovim 0.12.6.

## TL;DR

- **Detect with shared-mime-info, not libmagic.** On Ubuntu the freedesktop
  shared-mime-info database (`/usr/share/mime`) is the desktop's source of truth
  for file types. GIO, `xdg-mime`, and `xdg-open` all use it to pick the default
  app. It checks the filename glob first and falls back to magic. `file`/libmagic
  looks only at content, so it reports Markdown as `text/plain` and Go source as
  `text/x-c`.
- **"Editable in nvim" = `is_a(type, text/plain)`** using shared-mime-info's
  subclass tree: `text/*` is implicitly a subclass of `text/plain`, and many
  `application/*` text formats (json, xml, yaml, toml, shellscript) explicitly
  descend from it. Watch out for HTML, SVG, PostScript, and RTF: they are also
  `text/plain` descendants, so add a small "always open externally" override.
- **Run detection in-process during `scan`.** Spawning a process per file costs
  2 to 14 ms per file. Reading the database in-process takes about 10 ms for all
  3,000 files.
- **Open with `vim.ui.open(abs_path)`.** It runs `xdg-open` through
  `vim.system{detach=true}` with stdout/stderr discarded. On GNOME `xdg-open`
  hands off to `gio open`, which returns in about 10 ms while the app keeps
  running.

## 1. Detection: the three mechanisms

### 1.1 `file --mime-type` (libmagic)

- `file` "tests each argument in an attempt to classify it. There are three sets
  of tests, performed in this order: filesystem tests, magic tests, and language
  tests. The first test that succeeds causes the file type to be printed."
  ([file(1), 5.46, DESCRIPTION](https://manpages.ubuntu.com/manpages/en/man1/file.1.html))
  It never looks at the filename. Content is the only input.
- Result: it has no idea what Markdown is. Its "language tests" are heuristics
  and can misfire, e.g. Go source → `text/x-c`.
- Its MIME vocabulary is libmagic's own and only loosely matches
  shared-mime-info. An empty file gives `inode/x-empty`, while GIO gives
  `application/x-zerosize`.

### 1.2 shared-mime-info (the freedesktop database)

The spec is the *Shared MIME-info Database* specification, v0.21
([specifications.freedesktop.org/shared-mime-info](https://specifications.freedesktop.org/shared-mime-info/latest/)).

**Recommended checking order** ([§2.12](https://specifications.freedesktop.org/shared-mime-info/latest/ar01s02.html)):

1. If the type is given explicitly, use it "instead of guessing."
2. "Otherwise, start by doing a glob match of the filename. Keep only globs with
   the biggest weight", then those with "the longest pattern." If "all the
   matching globs result in the same mimetype, use that mimetype as the result."
3. "If the glob matching fails or results in multiple conflicting mimetypes,
   read the contents of the file" and run magic. "If there was no glob match,
   use the magic match as the result."
4. Fallback: "application/octet-stream for binary data, or text/plain for
   textual data". "Checking the first 128 bytes of the file for ASCII control
   characters is a good way to guess", and "files with high-bit-set characters
   should still be treated as text."

The glob always wins when it is unambiguous. A Markdown file named
`misnamed.pdf` is reported as `application/pdf` (see 1.4). That suits a catalog
of the user's own files: extensions are intentional.

**Subclassing** ([§2.11](https://specifications.freedesktop.org/shared-mime-info/latest/ar01s02.html#subclassing)):
"All text/* types are subclasses of text/plain." "All streamable types (ie,
everything except the inode/* types) are subclasses of application/octet-stream."
Other subclass relations come from the `sub-class-of` element and are compiled
into `/usr/share/mime/subclasses`.

**On this machine** `/usr/share/mime/text/markdown.xml` contains:

```xml
<sub-class-of type="text/plain"/>
<glob pattern="*.md"/> <glob pattern="*.mkd"/> <glob pattern="*.markdown"/>
<alias type="text/x-markdown"/>
```

and `globs2` has `50:text/markdown:*.md`. Some explicit `text/plain`
descendants from `/usr/share/mime/subclasses`:

| type | parent(s) |
|---|---|
| `text/markdown`, `text/csv`, `text/x-go`, `text/org`, `text/html`, `text/vnd.graphviz` | `text/plain` |
| `application/json` | `application/json5` → `text/javascript` → `text/plain` |
| `application/x-ipynb+json` | `application/json` → ... → `text/plain` |
| `application/x-shellscript`, `application/yaml`, `application/toml`, `application/xml` | `text/plain` |
| `image/svg+xml` | `application/xml` → `text/plain` |
| `application/postscript`, `application/rtf`, `application/x-desktop` | `text/plain` |
| `application/pdf`, `image/png` | (none: only implicitly `application/octet-stream`) |

**Front ends to the database:**

- **GIO** (`gio info -a standard::content-type`). GLib's implementation of the
  spec, and what GNOME and `gio open` use. `standard::fast-content-type` is
  glob-only: extensionless files come back as `application/octet-stream`.
  `g_content_type_is_a(type, supertype)` "Determines if `type` is a subset of
  `supertype`" ([docs.gtk.org](https://docs.gtk.org/gio/func.content_type_is_a.html)).
- **`xdg-mime query filetype`** is a shell wrapper. In `/usr/bin/xdg-mime`
  (1.2.1), `info_gnome` runs `gio info ... | grep standard::content-type`. When
  no desktop is detected, `info_generic` runs `mimetype --brief --dereference`
  (Perl File::MimeInfo, which also reads shared-mime-info) if it is installed,
  otherwise `/usr/bin/file --brief --dereference --mime-type`. **So on a
  headless box without `mimetype`, `xdg-mime` silently falls back to libmagic
  and Markdown becomes `text/plain` again.** `mimetype` is installed on this
  machine, so the generic path still returned `text/markdown` here.

### 1.3 Library options for the new CLI (Go or Rust)

- **Go stdlib `mime.TypeByExtension`.** On Unix,
  `$GOROOT/src/mime/type_unix.go` loads `/usr/local/share/mime/globs2` then
  `/usr/share/mime/globs2` (it cites the shared-mime-info spec), and falls back
  to `/etc/mime.types` only if neither exists. It keeps only simple `*.ext`
  globs, the first (highest-weight) one per extension. It ignores user-level
  `~/.local/share/mime`, magic, aliases, and subclasses. It also appends
  `; charset=utf-8` to `text/*` results (`text/markdown; charset=utf-8`), so
  strip parameters with `mime.ParseMediaType`. Content fallback:
  `net/http.DetectContentType` (WHATWG sniffing: text/plain vs a few binary
  formats). For `is_a`, parse `/usr/share/mime/subclasses` and `aliases` (a few
  hundred lines; 510 subclass lines here) and add the implicit `text/*` →
  `text/plain` rule.
- **Rust `xdg-mime` crate** (0.4.0, [docs.rs](https://docs.rs/xdg-mime/latest/xdg_mime/struct.SharedMimeInfo.html)).
  A full spec implementation: `guess_mime_type()` (name + data + path),
  `get_mime_types_from_file_name`, `get_mime_type_for_data`,
  `mime_type_subclass`, `get_parents`, `unalias_mime_type`. It reads the
  standard XDG base dirs, including user overrides.
- (Not evaluated: libmagic bindings. Per 1.1, libmagic is the wrong source of
  truth for this purpose anyway.)

### 1.4 Empirical comparison (sample files in a temp dir)

| file | `file --mime-type` | `xdg-mime query filetype` | `gio` content-type | `gio` fast-content-type |
|---|---|---|---|---|
| `a.txt` | text/plain | text/plain | text/plain | text/plain |
| `b.md` | **text/plain** | text/markdown | text/markdown | text/markdown |
| `fm.md` (YAML frontmatter) | **text/plain** | text/markdown | text/markdown | text/markdown |
| `c.csv` | text/plain | text/csv | text/csv | text/csv |
| `m.go` | **text/x-c** | text/x-go | text/x-go | text/x-go |
| `s.sh` | text/x-shellscript | application/x-shellscript | application/x-shellscript | application/x-shellscript |
| `j.json` | application/json | application/json | application/json | application/json |
| `d.pdf` | application/pdf | application/pdf | application/pdf | application/pdf |
| `i.png` | image/png | image/png | image/png | image/png |
| `noext` (markdown text) | text/plain | text/plain | text/plain | **application/octet-stream** |
| `pdf_noext` (PDF bytes) | application/pdf | application/pdf | application/pdf | **application/octet-stream** |
| `misnamed.pdf` (markdown text) | text/plain | **application/pdf** | **application/pdf** | application/pdf |
| `empty.md` (0 bytes) | inode/x-empty | application/x-zerosize | application/x-zerosize | application/x-zerosize |

Go `mime.TypeByExtension`: `.md` → `text/markdown; charset=utf-8`, `.go` →
`text/x-go; charset=utf-8`, `.org` → `text/org; charset=utf-8`, `.pdf` →
`application/pdf`, unknown → `""`.

Takeaways: content sniffing cannot tell Markdown from plain text, and nothing
in the file says it is Markdown, so the glob (extension) is the only reliable
signal. Extensionless files need magic or the text heuristic. Empty files
become `application/x-zerosize`, which is *not* a `text/plain` descendant, so
an empty `.md` would be classed non-editable unless special-cased (use the
glob result when size is 0).

## 2. Performance for `scan` (3,000 files: 1,000 each .md/.txt/.pdf)

| method | wall time | per file |
|---|---|---|
| Go in-process: `TypeByExtension` + 512-byte read + `DetectContentType` | **9.3 ms** total | ~3 µs |
| `file --mime-type -b -- *` (one process) | 0.67 s | ~0.2 ms |
| `gio info -a standard::content-type -- *` (one process) | 1.84 s | ~0.6 ms |
| `file --mime-type` one process per file | 6.4 s | ~2.1 ms |
| `xdg-mime query filetype` per file (300-file sample) | 4.1 s / 300 | **~14 ms** (≈41 s for 3k) |

Per-file subprocesses are fine for one `add` and too slow for `scan`. Batched
`gio info` would work but couples the CLI to output parsing and a GLib binary.
In-process detection costs nothing compared with the content hashing `scan`
already has to do.

## 3. Opening a non-text file

### 3.1 `xdg-open` vs `gio open`

- `xdg-open` "opens a file or URL in the user's preferred application ... for
  use inside a desktop session only." It "can not handle arguments that begin
  with a '-'", so pass absolute paths or `file://` URLs
  ([xdg-open(1)](https://manpages.ubuntu.com/manpages/en/man1/xdg-open.1.html)).
- In `/usr/bin/xdg-open` 1.2.1, `open_gnome3`/`open_gnome` simply run
  `gio open "$1"`. `open_generic` (no DE detected) uses `xdg-mime query
  filetype` + `.desktop` lookup, then `run-mailcap`, `mimeopen`, then `$BROWSER`.
  `xdg-open` is the portable wrapper. On Ubuntu GNOME it *is* `gio open`.
- `gio open` "Opens files with the default application that is registered to
  handle files of this type. GIO obtains this information from the
  shared-mime-info database, with per-user overrides stored in
  $XDG_DATA_HOME/applications/mimeapps.list" ([gio(1)](https://manpages.ubuntu.com/manpages/en/man1/gio.1.html)).
  The library equivalent is `g_app_info_launch_default_for_uri[_async]`, which
  also goes through the desktop portal when sandboxed
  ([docs.gtk.org](https://docs.gtk.org/gio/type_func.AppInfo.launch_default_for_uri_async.html)).
- Defaults here: `application/pdf` → `org.gnome.Papers.desktop`;
  `text/markdown` and `text/plain` → `org.gnome.TextEditor.desktop`. **The
  plugin must branch on type *before* calling the opener**, or Markdown would
  open in GNOME Text Editor instead of nvim.

**Non-blocking, verified.** In a sandbox (`XDG_CONFIG_HOME`/`XDG_DATA_HOME`
pointing at a temp dir, with a fake `application/pdf` handler that sleeps 3 s
then writes a marker file), both `gio open d.pdf` and `xdg-open d.pdf` exited
rc=0 in **8 ms / 14 ms**. The marker was absent at return and present 4 s
later: the opener returns at once and the app keeps running on its own. Note:
`gio open` on a file with an unknown extension and text content returned rc=0,
because the text heuristic made it `text/plain`, and launched the text editor.
Exit 0 means "launched something", not "found a specific handler".

### 3.2 Launching detached from Neovim

`vim.ui.open({path}, {opt})` "Opens `path` with the system default handler
(macOS `open`, Windows `explorer.exe`, Linux `xdg-open`, …), or returns (but
does not show) an error message on failure." It returns
`(vim.SystemObj?, string?)`. Also available as `:Open`.
(`:help vim.ui.open()`, `runtime/doc/lua.txt`, Neovim 0.12.6.)

Source (`runtime/lua/vim/ui.lua`, 0.12.6):

```lua
local job_opt = { text = true, detach = true }
...
if open_cmd[1] == 'xdg-open' then
  job_opt.stdout = false
  job_opt.stderr = false
end
return vim.system(cmd, job_opt), nil
```

`_get_open_cmd()` on Linux picks `xdg-open`, falling back to `wslview`,
`explorer.exe`, `lemonade`. `opt.cmd` overrides the command (e.g.
`{ cmd = { 'gio', 'open' } }`). It is asynchronous by default, detached (`:help vim.system()`:
`detach` makes the child a process-group leader so it keeps running after nvim
exits), and swallows stdout/stderr so
GUI app noise never reaches the editor. Errors come back as a return value,
so the caller has to `vim.notify` them. There is no need to hand-roll
`jobstart({detach=true})` or `setsid`.

## 4. Recommended approach

**Detection (CLI, at `add`/`scan` time, stored as the Resource's media type):**

1. Use the shared-mime-info algorithm in-process. In Go: `mime.TypeByExtension`
   (reads `globs2`), strip parameters, and when it is empty fall back to a
   512-byte sniff (`http.DetectContentType`, or a magic library if more binary
   formats matter), else `application/octet-stream`. In Rust: the `xdg-mime`
   crate's `guess_mime_type()`. Keep it behind a small `Detector` seam (the map
   wants OS-specific pieces isolated).
2. Do **not** use `file`/libmagic as the primary detector, and do **not**
   shell out per file.
3. Special-case size 0 by using the glob result (avoid
   `application/x-zerosize`).
4. Normalise aliases (`text/x-markdown` → `text/markdown`) via
   `/usr/share/mime/aliases`.

**Editable rule (CLI computes it, so the plugin stays dumb):**

- `editable = is_a(type, "text/plain")`, using `/usr/share/mime/subclasses`
  transitively plus the implicit `text/*` rule, minus a small configurable
  "open externally" list (default suggestion: `text/html`, `image/svg+xml`,
  `application/postscript`, `application/rtf`). Emit it as a boolean (e.g.
  `"editable": true`) in the CLI's JSON output so the Telescope picker never
  needs the MIME tree.

**Opening (Neovim plugin):**

- `editable` → `:edit <path>` in a buffer.
- otherwise → `vim.ui.open(vim.fn.fnamemodify(path, ':p'))` (absolute path,
  avoiding xdg-open's leading-dash problem), and `vim.notify` the returned
  error string if there is one. Optionally allow a user `opener` command passed
  through `opt.cmd`.
- An optional CLI `open <id>` command should run the same `xdg-open <abs>`
  (detached, stdio to `/dev/null`) for non-nvim front ends. That gives one
  opener for both front ends: `xdg-open`, which on GNOME is `gio open`.
