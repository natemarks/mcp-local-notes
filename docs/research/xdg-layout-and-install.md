# Research: XDG base-dir layout and user-wide install conventions

**Date:** 2026-10-24
**Issue:** [#52 XDG base-dir layout and user-wide install conventions](https://github.com/natemarks/mcp-local-notes/issues/52)
(child of map issue [#48](https://github.com/natemarks/mcp-local-notes/issues/48),
"Local file ontology CLI + Neovim finder: v1 spec")
**Scope:** Primary-source research only. No code was changed. Target is
Ubuntu 26.04 only. The language is Go or Rust (not decided yet). `<app>`
below is a placeholder for the new tool's name.

## TL;DR

- **Canonical store** (DB): `$XDG_DATA_HOME/<app>/` (default `~/.local/share/<app>/`).
  It is the user's important, irreplaceable data. Back it up.
- **Config**: `$XDG_CONFIG_HOME/<app>/config.toml` (default `~/.config/<app>/`).
  It is optional. The tool must run with built-in defaults when it is missing.
- **Logs, history, last-scan bookmarks**: `$XDG_STATE_HOME/<app>/` (default
  `~/.local/state/<app>/`).
- **Rebuildable indexes and caches**: `$XDG_CACHE_HOME/<app>/` (default `~/.cache/<app>/`).
  Only data that can be regenerated from the store goes here. Deleting it must
  cost nothing but time.
- **Binary**: `~/.local/bin/<app>`. On Ubuntu this is already on `PATH` via
  `~/.profile`, but only if the directory existed at login.
- **Git-friendly export**: default `$XDG_DATA_HOME/<app>/export/`. It is
  user-relocatable via config, because the user owns that git repo.
- Both candidate languages have a mature, spec-correct resolver. Go has
  `github.com/adrg/xdg`, because the Go stdlib only covers config and cache.
  Rust has `dirs` or `directories`.

## 1. What the XDG Base Directory spec says

Source: [XDG Base Directory Specification, v0.8 (8 May 2021)](https://specifications.freedesktop.org/basedir/latest/).

| Variable | Default if unset/empty | Spec's definition |
|---|---|---|
| `XDG_DATA_HOME` | `$HOME/.local/share` | "base directory relative to which user-specific data files should be stored" |
| `XDG_CONFIG_HOME` | `$HOME/.config` | "user-specific configuration files" |
| `XDG_STATE_HOME` | `$HOME/.local/state` | "state data that should persist between (application) restarts, but that is not important or portable enough to the user that it should be stored in `$XDG_DATA_HOME`". Examples: "actions history (logs, history, recently used files, …)" and "current state of the application that can be reused on a restart (view, layout, open files, undo history, …)" |
| `XDG_CACHE_HOME` | `$HOME/.cache` | "user-specific non-essential data files" |
| `XDG_RUNTIME_DIR` | (no default; set by the login session) | "user-specific non-essential runtime files". Mode "MUST be 0700" |
| `XDG_DATA_DIRS` | `/usr/local/share/:/usr/share/` | system search path, lower precedence than `XDG_DATA_HOME` |
| `XDG_CONFIG_DIRS` | `/etc/xdg` | system search path, lower precedence than `XDG_CONFIG_HOME` |

Rules that matter for implementation:

- "All paths set in these environment variables must be absolute." If a path
  is relative, the implementation "should consider the path invalid and ignore
  it", which means falling back to the default.
- An empty value is treated as unset ("either not set or empty").
- When writing into a missing directory, "an attempt should be made to create
  it with permission 0700."
- "User-specific executable files may be stored in `$HOME/.local/bin`.
  Distributions should ensure this directory shows up in the UNIX `$PATH`."
  The spec defines **no** `XDG_BIN_HOME` variable. Some libraries support one
  as a non-standard extension (see section 4).

## 2. What systemd / UAPI file-hierarchy says about `$HOME`

`file-hierarchy(7)` now defers to the UAPI Group's
[Linux File System Hierarchy (UAPI.9)](https://uapi-group.org/specifications/specs/linux_file_system_hierarchy/)
([file-hierarchy(7)](https://www.freedesktop.org/software/systemd/man/latest/file-hierarchy.html)).
Its "Home Directory" section:

- `~/.cache/`: "Persistent user cache data. User programs may place
  non-essential data in this directory. Flushing this directory should have no
  effect on operation of programs, except for increased runtimes necessary to
  rebuild these caches."
- `~/.config/`: "Application configuration. When a new user is created, this
  directory will be empty or not exist at all. Applications should fall back
  to defaults should their configuration in this directory be missing."
- `~/.local/bin/`: "Executables that shall appear in the user's `$PATH`
  search path. It is recommended not to place executables in this directory
  that are not useful for invocation from a shell; these should be placed in a
  subdirectory of `~/.local/lib/` instead. Care should be taken when placing
  architecture-dependent binaries in this place, which might be problematic if
  the home directory is shared between multiple hosts with different
  architectures."
- `~/.local/lib/`: "Static, private vendor data that is compatible with all
  architectures." (`~/.local/lib/<arch-id>/` is for public dynamic libraries.)
- `~/.local/share/`: "Resources shared between multiple packages, such as
  fonts or artwork."
- `~/.local/state/`: "Application state. ... Applications should fall back to
  defaults should their state in this directory be missing."

Each entry also says: if the matching `$XDG_*` variable is set, use it
instead.

Takeaways:

- `~/.cache` has a hard contract that flushing it is harmless. So only data
  that can be regenerated goes there.
- `~/.local/state` must also tolerate being missing. This rules it out for the
  canonical store, which fits the XDG wording "not important or portable
  enough".
- The UAPI wording for `~/.local/share` ("shared between multiple packages")
  is narrower than the XDG spec's "user-specific data files". In practice the
  XDG reading is the one tools follow: zoxide, `directories::ProjectDirs::data_dir`
  and Go's `adrg/xdg.DataFile` all put per-app data there. So the store
  belongs in `$XDG_DATA_HOME/<app>/`.
- A single static binary in `~/.local/bin` is fine. The architecture caveat
  only matters for homes shared across machines, which the single-machine
  decision rules out.

## 3. Ubuntu 26.04 specifics (verified on this machine)

- `/etc/os-release`: `Ubuntu 26.04.1 LTS`.
- The session sets `XDG_CONFIG_DIRS`, `XDG_DATA_DIRS`, `XDG_RUNTIME_DIR=/run/user/<uid>`
  and others. It leaves `XDG_CONFIG_HOME`, `XDG_DATA_HOME`, `XDG_STATE_HOME`
  and `XDG_CACHE_HOME` **unset**. So the tool will almost always land on the
  spec defaults. It still has to honour the variables, and tests should set
  them to temp dirs.
- `/etc/skel/.profile` (copied into each new user's `~/.profile`):

  ```sh
  # set PATH so it includes user's private bin if it exists
  if [ -d "$HOME/.local/bin" ] ; then
      PATH="$HOME/.local/bin:$PATH"
  fi
  ```

  So `~/.local/bin` is on `PATH`, ahead of system dirs, but **only if the
  directory existed when the login shell started**. An installer that creates
  `~/.local/bin` for the first time should warn that a re-login (or
  `source ~/.profile`) is needed, as zoxide's installer does (section 5).

## 4. How the Go and Rust libraries resolve paths

### Go

- **stdlib `os`** ([pkg.go.dev/os](https://pkg.go.dev/os#UserConfigDir)):
  - `UserConfigDir()` returns "`$XDG_CONFIG_HOME` ... if non-empty, else `$HOME/.config`".
  - `UserCacheDir()` returns "`$XDG_CACHE_HOME` ... if non-empty, else `$HOME/.cache`".
  - Both return an **error** "if the location cannot be determined (for
    example, `$HOME` is not defined) or the path in `$XDG_..._HOME` is
    relative". That is stricter than the spec, which says to ignore a relative
    path and fall back.
  - There is **no `UserDataDir` or `UserStateDir`**. The stdlib alone cannot
    place the store or the logs correctly.
- **[`github.com/adrg/xdg`](https://pkg.go.dev/github.com/adrg/xdg)** (latest
  tag v0.5.3, released 2024-10-31; MIT):
  - Exposes `DataHome`, `ConfigHome`, `StateHome`, `CacheHome`, `RuntimeDir`,
    `DataDirs` and `ConfigDirs`, plus the non-standard `BinHome`
    (`XDG_BIN_HOME`, default `~/.local/bin`).
  - Defaults from source (`paths_unix.go`): `~/.local/share`, `~/.config`,
    `~/.local/state`, `~/.cache`, `/run/user/$UID`.
  - `internal/pathutil.EnvPath` accepts an env value only if it is non-empty
    and `filepath.IsAbs`. Otherwise it uses the default, which is spec-correct.
  - `DataFile`, `ConfigFile`, `StateFile` and `CacheFile("<app>/x")` create
    missing parent directories. The `Search*File` variants only look up files
    and never create anything.
  - Values are read once at package init. Tests that change env vars must call
    `xdg.Reload()`.

### Rust

- **[`dirs`](https://docs.rs/dirs/latest/dirs/)** (7.0.0). The Linux source
  (`dirs-rs/src/lin.rs`) is one line per directory:
  - `config_dir` → `XDG_CONFIG_HOME` or `~/.config`
  - `data_dir` (and `data_local_dir`) → `XDG_DATA_HOME` or `~/.local/share`
  - `state_dir` → `XDG_STATE_HOME` or `~/.local/state`
  - `cache_dir` → `XDG_CACHE_HOME` or `~/.cache`
  - `executable_dir` → `XDG_BIN_HOME` or `~/.local/bin`
  - `runtime_dir` → `XDG_RUNTIME_DIR` (`None` if unset)

  Each value is filtered through `dirs_sys::is_absolute_path`. So relative
  values (and empty ones, which are not absolute) fall back to the default,
  which is spec-correct.
- **[`directories`](https://docs.rs/directories/latest/directories/struct.ProjectDirs.html)**
  (6.0.0), the same authors' higher-level API:
  - `ProjectDirs::from(qualifier, organization, application)`. On Linux only
    the application name is used: `("com","Foo Corp","Bar App")` gives
    `~/.config/barapp`.
  - It provides `config_dir`, `data_dir`, `data_local_dir`, `cache_dir`,
    `state_dir` and `runtime_dir`, already suffixed with the app name.
    `state_dir` and `runtime_dir` return `Option`.
- **Precedent:** zoxide uses `dirs::data_local_dir().join("zoxide")`, with an
  absolute-path-only `_ZO_DATA_DIR` override (`src/config.rs`).

**Conclusion:** both languages give a correct XDG resolver in one dependency
(`adrg/xdg` for Go, `dirs`/`directories` for Rust). This does not tip the
language choice either way. Whichever is chosen, put path resolution behind
one small `paths` module (seam). That keeps macOS possible later.
`directories`/`dirs` already map to `~/Library/...` there.

## 5. How comparable tools lay out their data

| Tool | Config | Data / DB | Other | Follows XDG? | Source |
|---|---|---|---|---|---|
| **zoxide** (Rust) | (none; env vars only) | `$XDG_DATA_HOME/zoxide` (`~/.local/share/zoxide`), override `_ZO_DATA_DIR` (must be absolute) | Installer default `--bin-dir` is `$HOME/.local/bin`. It warns if that is not on `$PATH` | Yes | [README](https://github.com/ajeetdsouza/zoxide), `src/config.rs`, `install.sh` |
| **zk** (Go) | Global `~/.config/zk/config.toml` (`ZK_CONFIG_DIR` or `XDG_CONFIG_HOME` override). Per-notebook `.zk/config.toml` inherits from it | SQLite index **inside the notebook**: `<notebook>/.zk/notebook.db` (`internal/cli/container.go`: `filepath.Join(path, ".zk/notebook.db")`) | Templates in `<notebook>/.zk/templates/` | Config only. Data lives next to the user's files | [docs/config/config.md](https://github.com/zk-org/zk/blob/main/docs/config/config.md), [docs/notes/notebook.md](https://github.com/zk-org/zk/blob/main/docs/notes/notebook.md) |
| **nb** (Bash) | `NBRC_PATH` default `~/.nbrc` | `NB_DIR` default `~/.nb` (notebooks are git repos) | User install: "add the `nb` script to your `$PATH`" (example `~/bin`) | No | `nb` script lines 455/476, [README](https://github.com/xwmx/nb) |
| **Taskwarrior** (C++/Rust) | `~/.taskrc`. If missing, falls back to `$XDG_CONFIG_HOME/task/taskrc` (`~/.config/task/taskrc`). `TASKRC` override | `data.location` default `~/.task` (`TASKDATA` override). Hooks in `~/.task/hooks` | | Config only (opt-in, added in TW #2290) | `src/Context.cpp`, `doc/man/taskrc.5.in` |
| **Atuin** (Rust) | **Now** `~/.atuin/config.toml` (`ATUIN_HOME`, `ATUIN_CONFIG_DIR`). **Formerly** `$XDG_CONFIG_HOME/atuin` | **Now** `~/.atuin`. **Formerly** `$XDG_DATA_HOME/atuin` (`~/.local/share/atuin`), still read as a legacy fallback | Daemon socket under `$XDG_RUNTIME_DIR` or `$TMPDIR/atuin-$UID/` | **Moved away** from XDG to a single dot-dir | [docs config.md](https://github.com/atuinsh/atuin/blob/main/docs/docs/configuration/config.md), `crates/atuin-common/src/dirs.rs` |

What the comparisons show:

- Only zoxide is fully XDG-native. The older tools (nb, Taskwarrior) use a
  single dot-dir. Atuin recently switched *from* XDG to `~/.atuin`, to keep
  all its files in one place.
- That migration is costly. `dirs.rs` has a nine-step lookup to avoid
  shadowing legacy files. The lesson: **choose the layout once in v1 and
  never move it.**
- zk keeps its index next to the user's files (`.zk/notebook.db`). That does
  not fit this project. Map #48 decided the tool "never writes into cataloged
  files" and metadata lives "only in the central store". So nothing goes
  under the cataloged roots, and everything goes under XDG dirs.
- Every tool offers one absolute-path env override for its main directory
  (`_ZO_DATA_DIR`, `NB_DIR`, `TASKDATA`, `ATUIN_HOME`). It costs little and
  makes tests and multiple profiles easy.

## 6. Where each artefact goes

| Artefact | Directory | Why |
|---|---|---|
| Canonical ontology store (SQLite or similar DB) | `$XDG_DATA_HOME/<app>/` | It is irreplaceable user data. Cache and state must both tolerate loss, so neither fits. |
| Git-friendly export | Default `$XDG_DATA_HOME/<app>/export/`, configurable `export.dir` | It is user data meant for backup and history. The user may want it in a git repo they keep elsewhere (e.g. `~/notes-ontology/`), so the path is config. |
| Rebuildable indexes (FTS, hash→path lookup, query caches) | `$XDG_CACHE_HOME/<app>/` | UAPI: flushing must only cost rebuild time. Only things that can be derived from the store plus the filesystem go here. Indexes *inside* the DB file stay with the DB. |
| Logs, command history, last-`scan` bookmarks | `$XDG_STATE_HOME/<app>/` | The XDG examples name "logs, history". Losing them must not break anything. |
| Config | `$XDG_CONFIG_HOME/<app>/config.toml` | Optional, with defaults when missing (UAPI). Search `XDG_CONFIG_DIRS` (`/etc/xdg/<app>/`) only if a system-wide default is ever wanted. Not needed for v1. |
| User-authored files the tool creates (vocabulary seed files, saved queries, templates) | Hand-editable, settings-like files → `$XDG_CONFIG_HOME/<app>/`. Content that is effectively data → `$XDG_DATA_HOME/<app>/` | Follows the XDG split: settings vs data. Concepts and relations belong in the store, not in loose files. |
| Locks / sockets (none expected, since there is no daemon) | `$XDG_RUNTIME_DIR/<app>/`, or a lock file next to the DB | Runtime dir is 0700 and cleared at logout. A DB-level lock (e.g. SQLite) usually makes a separate lock file unnecessary. |
| Binary | `~/.local/bin/<app>` | XDG and UAPI both say so, and Ubuntu's `~/.profile` puts it on `PATH`. |

## 7. Install conventions for `~/.local/bin`

- `go install` puts binaries in "`GOBIN` ... which defaults to `$GOPATH/bin`
  or `$HOME/go/bin`" ([cmd/go](https://pkg.go.dev/cmd/go)). That is **not**
  `~/.local/bin`. For a user-wide install use
  `GOBIN=$HOME/.local/bin go install ...`.
- `cargo install` root precedence: "`--root` option, `CARGO_INSTALL_ROOT`,
  `install.root` config, `CARGO_HOME`, `$HOME/.cargo`"
  ([Cargo Book](https://doc.rust-lang.org/cargo/commands/cargo-install.html)).
  Binaries go in `<root>/bin`, so `cargo install --root ~/.local` lands them
  in `~/.local/bin`.
- Prebuilt release tarballs with a `make install` / install-script default of
  `$HOME/.local/bin`, overridable with `--bin-dir` / `PREFIX`, match zoxide's
  `install.sh`. They need no Go or Rust toolchain. Warn if the directory is
  not on `$PATH` (section 3 gotcha).
- No sudo, and nothing under `/usr/local`. User-wide means `$HOME` only.
- The Neovim plugin is installed by lazy.nvim into Neovim's own
  `stdpath("data")`. The tool does not manage that path. The plugin only
  needs the binary on `PATH`, or a configurable `cmd` option.

## 8. Recommended layout (concrete)

Assume `<app>` is the binary name and the defaults hold (XDG vars unset, as on
this machine).

| Purpose | Resolved via | Default path on Ubuntu 26.04 | Safe to delete? | Back up? |
|---|---|---|---|---|
| Binary | install target (`XDG_BIN_HOME` if a lib supports it) | `~/.local/bin/<app>` | reinstall | no |
| Config | `XDG_CONFIG_HOME` | `~/.config/<app>/config.toml` | yes (defaults apply) | optional |
| Canonical store | `XDG_DATA_HOME` | `~/.local/share/<app>/store.db` | **no** | **yes** |
| Export (git repo) | config `export.dir`, default under `XDG_DATA_HOME` | `~/.local/share/<app>/export/` | yes if the store is intact (re-export) | yes (that's its job) |
| Rebuildable caches/indexes | `XDG_CACHE_HOME` | `~/.cache/<app>/` | yes (rebuild cost only) | no |
| Logs / history / scan state | `XDG_STATE_HOME` | `~/.local/state/<app>/<app>.log` | yes | no |
| Runtime (if ever needed) | `XDG_RUNTIME_DIR` | `/run/user/<uid>/<app>/` | cleared at logout | no |

Implementation rules:

1. Resolve every path in one `paths` module. Use `adrg/xdg` for Go, or
   `dirs`/`directories` for Rust. Do not read `XDG_*` directly anywhere else.
2. Honour XDG vars only if they are absolute and non-empty. Otherwise fall
   back. Both recommended libraries already do this. Go's stdlib errors
   instead.
3. Create missing directories with mode `0700`.
4. Provide one override, `<APP>_DATA_DIR` (absolute only), for the store
   location, as zoxide (`_ZO_DATA_DIR`) and Taskwarrior (`TASKDATA`) do. Plus
   a `--config` flag. Tests set `XDG_*_HOME` to temp dirs.
5. Never write under cataloged Resource roots. No zk-style `.app/` dir.
6. Expose resolved paths through a command (e.g. `<app> paths --json`) so
   users, the Neovim plugin and bug reports can see them.
7. Freeze this layout in v1. Atuin's XDG→`~/.atuin` migration shows the cost
   of moving later.
