# Packaging (macOS)

Ships audiohook as a double-click installer in a `.dmg`. The installer does the real
setup (clone, venv, deps, LaunchAgents), which is the supported path for MLX. A fully
frozen self-contained `.app` is possible but is left as a future option, see the note.

## Build the installer .dmg

    ./package/build_dmg.sh           # -> audiohook-installer.dmg

The image contains `Install audiohook.command`. Built with the system `hdiutil`, no extra
tooling. For a Gatekeeper-clean image, sign and notarize it (commented commands in
`build_dmg.sh`, needs an Apple Developer ID). For personal use you can skip that and
right-click the installer the first time.

## What the installer does

`install.command` (re-runnable):
1. Clones (or fast-forwards) the repo into `~/audiohook/app`.
2. `brew install ffmpeg espeak-ng`.
3. Creates a venv and installs `requirements.txt` + `mlx-audio`, downloads the spaCy model.
4. Points the app at `~/audiohook/inbox` and `~/audiohook/library`.
5. Fills the LaunchAgent templates with real paths and loads them (worker, inbox, pull).

Override locations with `AUDIOHOOK_HOME` and `AUDIOHOOK_REPO`. After install, drop an
EPUB in `~/audiohook/inbox` and the M4B appears in `~/audiohook/library`.

## Note: fully frozen .app (future)

A self-contained `.app` (no system Python or pip needed) can be built with `py2app` or
`PyInstaller`, then wrapped with this same `.dmg` step. It is not done here because
freezing MLX is fiddly: the bundler must include MLX's Metal shader libraries
(`*.metallib`), the spaCy model data, and misaki's lexicon data, and it needs iteration on
an actual Mac. The installer approach above avoids all of that by using the normal pip
install path. Revisit freezing only if zero-dependency distribution is needed.
