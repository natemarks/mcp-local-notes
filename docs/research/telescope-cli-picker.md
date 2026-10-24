# Research: a Telescope picker over an external CLI in Neovim 0.12

Issue: [#53 Telescope picker over an external CLI in Neovim 0.12](https://github.com/natemarks/mcp-local-notes/issues/53)
(child of map issue [#48](https://github.com/natemarks/mcp-local-notes/issues/48))

Question: how should a lazy.nvim-installable plugin for Neovim 0.12 drive a
Telescope picker from an external CLI's JSON output? Constraints from the map:
the plugin is **read-only** (query, pick, open), it consumes the CLI's JSON, the
CLI is Go or Rust, Ubuntu 26.04 only, and the corpus is under 10k Resources.

## Sources and versions

All claims were checked against the installed sources, which match what the
user actually runs:

| Source | Version | Where |
|---|---|---|
| Neovim runtime docs + Lua | v0.12.6 | `:h vim.system()`, `:h vim.ui.open()`, `:h vim.ui.select()`, `:h vim.json.decode()`, `:h lua-loop-callbacks`, `:h lua-plugin`, `:h health-dev`, `:h news` (`$VIMRUNTIME/doc/*.txt`, `$VIMRUNTIME/lua/vim/ui.lua`) |
| telescope.nvim | [`40aedd8a`](https://github.com/nvim-telescope/telescope.nvim/tree/40aedd8a68c78a656a10a8d62d80c54af59420fb) | [`developers.md`](https://github.com/nvim-telescope/telescope.nvim/blob/40aedd8a68c78a656a10a8d62d80c54af59420fb/developers.md), `lua/telescope/finders.lua`, `finders/async_oneshot_finder.lua`, `finders/async_job_finder.lua`, `async_job.lua`, `previewers/buffer_previewer.lua`, `previewers/utils.lua`, `config.lua` |
| lazy.nvim | [`85c7ff37`](https://github.com/folke/lazy.nvim/tree/85c7ff3711b730b4030d03144f6db6375044ae82) | `doc/lazy.nvim.txt` (Plugin spec, Packages, Developers, Minit), `lua/lazy/core/loader.lua`, `lua/lazy/core/cache.lua` |
| plenary.nvim | [`74b06c6c`](https://github.com/nvim-lua/plenary.nvim/tree/74b06c6c75e4eeb3108ec01852001636d85a932b) | [`TESTS_README.md`](https://github.com/nvim-lua/plenary.nvim/blob/74b06c6c75e4eeb3108ec01852001636d85a932b/TESTS_README.md) |
| telescope-ui-select.nvim | `6e51d7da` | source grep |
| User config | `~/.config/nvim` (read only) | kickstart-derived, lazy.nvim |

## 0. The user's conventions (from `~/.config/nvim`)

- **Spec layout.** Each plugin gets a directory `lua/custom/plugins/<name>/`
  with `init.lua` (the lazy spec, returned as a table), `config.lua` (an
  `M.setup()` that calls the plugin's `setup`) and `keymaps.lua` (an
  `M.setup()` that sets maps). `init.lua` calls both from `config = function() ... end`.
  `init.lua` at the root `require`s each spec explicitly
  (`require 'custom.plugins.telescope'`), plus `{ import = 'custom.plugins' }`.
- **Telescope setup.** `telescope.nvim` on `event = 'VimEnter'`, with
  `plenary.nvim`, `telescope-fzf-native.nvim` (`build = 'make'`, `cond` on
  `make` being executable) and `telescope-ui-select.nvim` (dropdown theme).
  Extensions are loaded with `pcall(require('telescope').load_extension, ...)`.
- **Keymaps.** Finders live under `<leader>f*` with `[F]ind [X]` descriptions.
  Already taken: `fh fk ff fb fs fw fg fd fr ft f. f/ fn` and `<leader><leader>`, `<leader>/`.
  `<leader>fo` (and `<leader>fO`) are free.
- **Shelling out.** The user's own `<leader>cj` map already uses the pattern
  this research recommends: check `vim.fn.executable`, run
  `vim.system({...}, { text = true }):wait()`, and on `result.code ~= 0`
  `vim.notify(result.stderr, vim.log.levels.ERROR)`.
- **Health.** `lua/custom/health.lua` uses `vim.health.start/ok/warn/error/info`
  and loops over executables with `vim.fn.executable`.
- **Testing.** `neotest` with `neotest-plenary` is installed, so plenary-busted
  specs in the plugin repo can be run from inside the user's editor.
- The user also has `<leader>fn` mapped to "Find Neovim files", so the picker
  should not claim `fn` for "notes".

A user-side spec that fits these conventions would be
`lua/custom/plugins/<name>/init.lua` returning
`{ '<owner>/<repo>', dependencies = { 'nvim-telescope/telescope.nvim' }, cmd = ..., keys = ..., opts = {...} }`.

## 1. Running the CLI: `vim.system` vs Telescope job finders

### What each one actually does

- **`vim.system(cmd, opts, on_exit)`** runs `cmd` directly (no shell), throws if
  `cmd` cannot be run, and returns a `SystemObj` with `:wait(timeout)`,
  `:kill()`, `:write()`. With `on_exit` it is async; `on_exit` receives
  `{ code, signal, stdout, stderr }`. `opts` include `cwd`, `env`, `text`
  (normalises `\r\n`), `timeout` (TERM on expiry, code 124), and `stdout`/`stderr`
  callbacks for streaming. (`:h vim.system()`, `:h SystemObj:wait()`)
- `on_exit` runs in a luv callback, where calling `vim.api` (other than
  `api-fast`) is an error (E5560); wrap with `vim.schedule_wrap`. (`:h lua-loop-callbacks`)
  `vim.json` is usable outside the main thread (`:h lua-loop-threading`), so
  decoding can happen before scheduling.
- **`finders.new_oneshot_job(command_list, opts)`** spawns the command once via
  `telescope.async_job`, reads stdout through a `LinesPipe`, and calls
  `entry_maker(line)` **per line** (`finders.lua` L189-211,
  `async_oneshot_finder.lua`). It is the right finder for `find`-style
  newline-separated output (`developers.md`, "Oneshot Job").
- **`finders.new_async_job{ command_generator = fn(prompt) }`** re-spawns the
  command **on every prompt change**, killing the previous job
  (`async_job_finder.lua`: `job:close(true)` then `fn_command(prompt)`). This is
  how `live_grep` works: the external process does the filtering, not
  Telescope's sorter.
- **Neither Telescope job finder surfaces failures.** `async_job.spawn` defaults
  `stderr` to a `NullPipe` (`async_job.lua` L22) and neither finder inspects the
  exit code, so a CLI error (missing DB, bad flag, schema mismatch) shows up as
  an empty picker with no message.
- **`finders.new_table{ results, entry_maker }`** takes an in-memory Lua list
  (`developers.md`, "First Picker" and "Entry Maker").

### Recommendation

Use **`vim.system` + `vim.json.decode` + `finders.new_table`** for the main
"pick a Resource" flow:

```lua
vim.system({ cli, 'find', '--json', unpack(args) }, { text = true }, vim.schedule_wrap(function(out)
  if out.code ~= 0 then
    return vim.notify(out.stderr, vim.log.levels.ERROR, { title = '<name>' })
  end
  local ok, doc = pcall(vim.json.decode, out.stdout, { luanil = { object = true, array = true } })
  if not ok then return vim.notify('bad JSON from ' .. cli, vim.log.levels.ERROR) end
  open_picker(doc.resources, opts)   -- pickers.new(opts, { finder = finders.new_table{...}, ... })
end))
```

Why:

1. Errors become visible (exit code + stderr), which the job finders discard.
2. The data set is small (<10k), so loading everything once and letting
   Telescope's configured sorter (`conf.generic_sorter(opts)`, which picks up the
   user's fzf-native sorter, `developers.md` L100-110) filter client-side is the
   simplest correct design. No re-spawn per keystroke.
3. The CLI can emit a single JSON document with an envelope (schema version,
   counts, warnings) rather than being constrained to one-record-per-line.
4. It is the same `vim.system` code path the `vim.ui.select` fallback (section 5)
   needs, so there is one data loader, not two.

Keep **`new_async_job`** in reserve only for a future "live query" picker where
the CLI must do the filtering (full-text search over text Resources, or a query
DSL, both still "Not yet specified" on the map). In that mode the CLI would emit
JSON Lines and the `entry_maker` would `vim.json.decode` each line.

## 2. JSON vs line output for large result sets

- At the stated scale a single JSON array is fine: 10k small objects is a few MB,
  and `vim.json.decode` is the built-in C decoder. Startup latency is dominated by
  the CLI's own query, not by decoding.
- Telescope's `display` should be a **function** for large lists so formatting
  only runs for visible rows (`developers.md` L231-234), and `entry_display.create`
  gives column layout (`developers.md` L236-238). `ordinal` is what the sorter
  matches, so make it `title .. ' ' .. tags .. ' ' .. path` to let fuzzy match
  hit any of them.
- Use `{ luanil = { object = true, array = true } }` so JSON `null` becomes Lua
  `nil` instead of `vim.NIL` (which is truthy and a common bug source).
  (`:h vim.json.decode()`)
- JSON Lines only pays off if results are streamed while the CLI is still
  running (`new_oneshot_job` shows rows as lines arrive). Not needed under 10k;
  the CLI can offer `--jsonl` later without breaking the plugin.

**CLI contract the plugin needs** (feed this into the CLI's output-schema ticket):
an object with `schema_version` and an array of Resources, each with at least
`id`, absolute `path`, `title`, `media_type` (the MIME type the CLI already
detects with libmagic), `tags`, `type`, and a `missing` flag (from `validate`).
The plugin must never re-derive these.

## 3. Previewers for text vs binary files

- Entries that set `path` (absolute) get file behaviour for free: `conf.file_previewer`
  previews them and the default select action `:edit`s them (`developers.md`
  L245-250, L254-258).
- Telescope's buffer previewer already guards binaries: if the filetype is
  unknown and `preview.check_mime_type` is on (default on non-Windows) it shells
  out to `file --mime-type -b`, and anything not `text/*`, `inode/*`, `*/json` or
  `*/javascript` is treated as binary and shows "Binary cannot be previewed".
  Files over `preview.filesize_limit` (25 MB) are not read, and previews time out
  after `preview.timeout` (250 ms). Hooks `mime_hook`, `filesize_hook`,
  `filetype_hook` let the user override. (`config.lua` L601-607,
  `buffer_previewer.lua` L147-213, `previewers/utils.lua` `binary_mime_type`)
- Because the CLI already knows `media_type`, the plugin should **not** pay a
  `file(1)` fork per highlighted row. Write a small `previewers.new_buffer_previewer`
  with `define_preview(self, entry)`:
  - text media type: delegate to `conf.buffer_previewer_maker(entry.path, self.state.bufnr, { bufname = self.state.bufname })`
    (gets treesitter highlighting and the size/time guards);
  - anything else: write a metadata card into the preview buffer (title, type,
    tags, relations, media type, size, path, "missing" warning) instead of file
    contents. This is also useful for text Resources, so consider a toggle
    between "content" and "metadata" previews.
  (`:h telescope.previewers`, `previewers/init.lua` `new_buffer_previewer`, `buffer_previewer_maker`)

## 4. Actions: open in a buffer vs the OS opener

- Replace the default action rather than mapping `<CR>` yourself, so the user's
  remaps of `select_default` still apply: `attach_mappings = function(prompt_bufnr, map) actions.select_default:replace(fn); return true end`.
  Returning `false` drops the default movement mappings. (`developers.md` L126-175)
- For split/tab variants, replace `action_set.select` (it receives `type` =
  `default|horizontal|vertical|tab`) or use `:replace_if(cond, fn)` so only
  non-text entries get the custom behaviour (`developers.md` L386-401).
- **`vim.ui.open(path)`** is the correct OS opener. On Linux it resolves to
  `xdg-open`, and it already spawns via `vim.system` with `detach = true` and
  `stdout`/`stderr` silenced for `xdg-open`. It returns `(SystemObj|nil, err|nil)`
  and does **not** display the error, so the caller must `vim.notify(err)`. It
  expands `~/` and env vars, and `opt.cmd` overrides the opener (that's the
  macOS/other-OS seam the map asks for). (`:h vim.ui.open()`, `$VIMRUNTIME/lua/vim/ui.lua` L178-227)
  0.12 also made `:checkhealth` report whether a `vim.ui.open()` handler exists (`:h news`, line 383).
- Recommended mapping: `<CR>` dispatches on `media_type` (text: `:edit`, else:
  `vim.ui.open`); `<C-o>` forces `vim.ui.open`; `<C-e>` forces `:edit`;
  `<C-y>` yanks the path. Missing Resources should notify "missing, run
  `<cli> relink`" rather than open an empty buffer.
- Actions stay read-only: nothing in the picker calls a mutating CLI subcommand.

## 5. `vim.ui.select` fallback when Telescope is absent

- `vim.ui.select(items, { prompt, format_item, kind, preview_item }, on_choice)`
  accepts arbitrary items. Plugins may override it, and they're expected to
  honour `format_item`/`preview_item`/`kind`. (`:h vim.ui.select()`)
- In 0.12 `vim.ui.select` documents a `preview_item` callback (returns `{ buf, pos, pos_end }`),
  but notes "the default `vim.ui.select` currently doesn't support preview", and
  `telescope-ui-select.nvim` (installed here) does not reference `preview_item`.
  So supply it for forward-compatibility, but don't count on previews in the fallback.
- Pattern: `local has_telescope = pcall(require, 'telescope')`. If true, run the
  Telescope picker; otherwise call `vim.ui.select(resources, { prompt = 'Resources', kind = '<name>.resource', format_item = fmt }, open_resource)`.
  The same `open_resource` dispatcher from section 4 is shared.
- Note for this user: with `telescope-ui-select` loaded, the "fallback" also
  renders as a Telescope dropdown. That makes it a free sanity test, not a
  degraded path.

## 6. Shipping the Lua plugin from the same repo as a compiled CLI

### lazy.nvim has no "subdirectory plugin" option

- A spec source is one of `[1]` (short URL), `dir`, or `url`, plus `name`/`dev`.
  There is no subdirectory key (`lazy.nvim.txt`, "Spec Source"). The plugin
  root is the clone root: module auto-loading walks `plugin.dir .. "/lua"`
  (`core/loader.lua` L233) and the module cache looks for top-level `/lua/*`
  under the plugin path (`core/cache.lua` L438-451).
- The only documented workaround is `config = function(plugin) vim.opt.rtp:append(plugin.dir .. "/custom-rtp") end`
  (packer `rtp` migration note). That runs too late for lazy's
  `require`-triggered autoloading and pushes the burden onto every user config.
  Don't use it.
- **So put the Neovim plugin at the repo root**, next to the Go/Rust sources:

```
<repo>/
├── cmd/<cli>/ or src/           # Go or Rust CLI
├── lua/<name>/
│   ├── init.lua                 # setup(opts), pick(opts), the vim.system loader
│   ├── cli.lua                  # resolve binary, run, decode, version check
│   ├── picker.lua               # Telescope picker (requires telescope lazily)
│   ├── select.lua               # vim.ui.select fallback
│   ├── actions.lua              # open dispatcher (edit vs vim.ui.open)
│   └── health.lua               # :checkhealth <name>
├── lua/telescope/_extensions/<name>.lua   # :Telescope <name>
├── plugin/<name>.lua            # tiny: user command(s) only, no eager require
├── doc/<name>.txt
├── lazy.lua                     # optional package spec, see below
└── tests/                       # plenary-busted specs + minimal_init.lua
```

  Prior art in the user's own config: `telescope-fzf-native.nvim` ships C
  sources at the root alongside `lua/` and builds via `build = 'make'`.

- **Telescope extension**: `lua/telescope/_extensions/<name>.lua` returning
  `require('telescope').register_extension{ setup = fn(ext_config, config), exports = { <name> = ... } }`
  makes `:Telescope <name>` work, and the user loads it with
  `pcall(require('telescope').load_extension, '<name>')` like their other
  extensions (`developers.md` L280-322).
- **`plugin/<name>.lua`** should only define commands (e.g. `:<Name> find`) that
  `require` on use. `:h lua-plugin-lazy` says plugins should do their own lazy
  loading this way and gives no benefit to user-side `cmd =`/`keys =`
  micro-management. Don't set default keymaps; document a suggested
  `<leader>fo`.
- **`lazy.lua`** at the repo root is lazy.nvim's recommended package spec
  (`lazy.nvim.txt` "Packages"/"Developers"): e.g.
  `return { '<owner>/<repo>', dependencies = { 'nvim-telescope/telescope.nvim' }, opts = {} }`.
  Don't ship a `*.rockspec`: lazy uses rockspecs only when the package has no
  `/lua`, a complex build, or deps, and would then try `luarocks make`.
- **Binary resolution.** The plugin should find the CLI on `$PATH` (`opts.cmd`,
  default `'<cli>'`, checked with `vim.fn.executable`) and not assume it lives in
  the plugin dir. A lazy `build` step can be offered as a convenience
  (`build = 'make install'` or `go build -o bin/<cli> ./cmd/<cli>`, then
  `opts.cmd = plugin.dir .. '/bin/<cli>'`). Build steps run async in a
  coroutine (`lazy.nvim.txt` "Building"). Whether that or a release binary is
  primary belongs to the map's open "Release & packaging" item.
- **Version handshake.** Have the CLI expose `<cli> version --json` (or carry
  `schema_version` in every JSON payload). The plugin declares the schema range
  it understands and errors clearly on mismatch. Repo-root co-location means
  plugin and CLI are versioned together, but a `$PATH` binary can still drift
  from the plugin commit lazy has checked out.

### `:checkhealth <name>`

`lua/<name>/health.lua` returning `{ check = function() ... end }` is found
automatically by `:checkhealth` (`:h health-dev`, `:h lua-plugin-troubleshooting`).
Check:

1. Neovim >= 0.12 (`vim.version.ge`), matching the user's own `custom/health.lua`.
2. Binary: `vim.fn.executable(opts.cmd)`, `vim.fn.exepath` for the resolved path.
3. Binary runs and the schema matches: `vim.system({cmd, 'version', '--json'}):wait(2000)`.
4. Store reachable: a cheap read-only call (e.g. `<cli> stats --json`), reporting counts and missing Resources.
5. Optional deps: `telescope` (warn, fallback in use), `vim.ui.open` handler / `xdg-open` (warn).
6. Config: unknown `opts` keys (the place `:h lua-plugin-config` suggests for typo detection).

## 7. Testing with plenary/busted

- **Harness**: plenary's busted runner, headless:
  `nvim --headless --noplugin -u tests/minimal_init.lua -c "PlenaryBustedDirectory tests/ { minimal_init = 'tests/minimal_init.lua' }"`.
  This is exactly how telescope.nvim tests itself (`Makefile`), and plenary
  bundles `luassert` with `stub`/`mock`/`spy` (`TESTS_README.md`). The user's
  `neotest-plenary` runs the same specs in-editor.
- An alternative is `lazy.minit.busted` (`nvim -l tests/busted.lua tests`), which
  installs real busted via hererocks and is how LazyVim tests (`lazy.nvim.txt`
  "Minit"). It's heavier (it bootstraps lazy over the network). Plenary is
  already a Telescope dependency, so prefer plenary.
- **What to test**, keeping each seam small:
  - `cli.lua`: decoding, error paths, `null` handling, schema mismatch. Use a
    **fake CLI** (a tiny shell script in `tests/fixtures/bin/` that prints
    golden JSON or exits non-zero) and point `opts.cmd` at it. No compiled binary needed.
  - `actions.lua`: stub `vim.ui.open` and `vim.cmd.edit` with `luassert.stub`,
    and assert text media types edit while others open, and that a missing Resource notifies.
  - `select.lua`: stub `vim.ui.select` and assert `format_item` output and that `on_choice` routes to the dispatcher.
  - `picker.lua`: construct the picker and assert entries via `entry_maker`
    (`display`/`ordinal`/`path`). Driving the live Telescope UI headless is
    brittle, so test the pure functions and leave the UI to a smoke test.
  - `health.lua`: run `require('<name>.health').check()` against the fake CLI.
- One end-to-end CI job can build the real CLI, seed a temp store, and run the
  same specs with `opts.cmd` pointed at it. This covers the CLI-plugin JSON
  contract, which is the seam most likely to break.

## Recommended plugin architecture

1. **One repo, plugin at the root.** `lua/<name>/`, `plugin/<name>.lua`,
   `lua/telescope/_extensions/<name>.lua`, `doc/`, `lazy.lua`, `tests/` sit
   beside the Go/Rust source. lazy.nvim cannot load a plugin from a
   subdirectory without user-side rtp hacks.
2. **The CLI owns all logic and emits versioned JSON.** The plugin is a thin,
   read-only adapter: `cli.lua` resolves the binary (`$PATH` by default, `opts.cmd`
   override), runs it with `vim.system` (async, `text = true`, timeout),
   surfaces `code`/`stderr` via `vim.notify`, decodes with `vim.json.decode`
   (`luanil`), and checks `schema_version`.
3. **Picker = `finders.new_table` over the decoded list + `conf.generic_sorter`**
   (respects fzf-native). Entries carry `value` (the full Resource), absolute
   `path`, a function `display` built with `entry_display`, and an `ordinal` of
   title + tags + type + path. Filters (`--tag`, `--type`, `--related-to`) are
   passed as CLI args from `pick(opts)`. `new_async_job` is held back for a
   future live-query picker.
4. **Previewer keyed on the CLI's `media_type`**: text goes to
   `conf.buffer_previewer_maker` (keeps Telescope's size/timeout guards), binary
   or missing gets a metadata card. There's no per-row `file(1)` probe.
5. **One open dispatcher shared by both front ends**: text `:edit`s, other types
   go to `vim.ui.open` (detached `xdg-open`, error notified). Actions are wired
   via `actions.select_default:replace`/`action_set.select:replace_if`, plus
   force-edit/force-open/yank-path mappings.
6. **`vim.ui.select` fallback** when `pcall(require, 'telescope')` fails, reusing
   the loader and dispatcher, with `format_item` and a `preview_item` for
   forward-compatibility.
7. **`:checkhealth <name>`** checks the Neovim version, the binary, the
   version/schema handshake, store reachability, the optional Telescope
   dependency and the opener.
8. **Tests**: plenary-busted, headless, with a fake-CLI fixture for unit specs
   and one CI job against the real binary for the JSON contract.
9. **User-side spec** (matching `~/.config/nvim` conventions):
   `lua/custom/plugins/<name>/{init,config,keymaps}.lua`, keymap `<leader>fo`
   ("[F]ind [O]ntology resources"), and `load_extension('<name>')` alongside
   `fzf`/`ui-select` in `custom/plugins/telescope/config.lua`.

Open items this hands to other tickets: the CLI's JSON output schema
(fields listed in section 2), binary distribution versus a lazy `build` step
(map: "Release & packaging"), and whether a live-query mode is needed (map:
"Query expressiveness").
