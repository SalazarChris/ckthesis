# AF3 JSON Builder

A local Windows application for building AlphaFold 3 **input JSON** configurations:
edit a base job, add protein, DNA, RNA and ligand entities, and generate one
independent AF3 configuration per entry of an input file.

This repository is the **builder only**. AF3 inference — the model weights, GPU
drivers and the server software — runs in a separate university Linux
environment. Nothing here installs or needs any of that.

## Install (once)

1. Put the application folder somewhere under your own user profile, for
   example `C:\Users\<you>\AF3Builder`. Do **not** put it in
   `C:\Program Files`: the setup creates a `.venv` inside the folder and
   Windows does not let an ordinary user write there.
2. Double-click **`setup_windows.bat`**. It finds Python, creates `.venv`,
   installs the project with its GUI and template extras, and runs the
   dependency check. The window stays open at the end — read the last lines.
3. If it reports a problem, read [`DEPENDENCY_SETUP.md`](DEPENDENCY_SETUP.md).
   Python 3.9+ is required; a python.org build is the verified choice.

## Launch

Double-click either launcher in the application folder:

| Launcher | What it opens |
| --- | --- |
| **`run_gui.cmd`** | The desktop window (the normal choice) |
| **`run_console.cmd`** | The text menu, for a terminal-style workflow |

Both work from any location — the folder is found from the launcher's own
path, so a desktop shortcut, the Start menu, Explorer and a terminal all
behave the same. A black console window stays behind the GUI on purpose: it is
where a startup error appears.

### Desktop or Start-menu shortcut

1. Right-click `run_gui.cmd` → **Show more options** → **Send to** →
   **Desktop (create shortcut)**.
2. Rename the shortcut to `AF3 Configuration Builder`.
3. Optional but recommended: right-click the shortcut → **Properties**, set
   **Start in** to the application folder (the launchers already change to
   their own folder, so this only helps other tools resolve relative paths).

There is no installer, and none is needed.

## Where your files go

Everything you save or generate goes to one output tree, **outside** the
application folder:

```text
C:\Users\<you>\Documents\AF3Builder\
    saved_jobs\                  one saved job JSON + its assets\
    generated_configurations\    batch output: one folder per configuration,
                                 plus manifest.json and asset copies
```

The same folder is used no matter where you started the program. If you want
it somewhere else — a USB stick, a network share, another drive — pick that
folder in the save/generate dialog once: the application remembers it for the
next time. The full precedence is:

1. the `AF3BUILDER_OUTPUT_ROOT` environment variable (an explicit override; a
   value that cannot be used is reported rather than silently ignored);
2. the last-used output folder, remembered in
   `%APPDATA%\AF3Builder\preferences.json`;
3. `Documents\AF3Builder`;
4. `%LOCALAPPDATA%\AF3Builder` when Documents is unavailable.

### Save vs. generate

- **Save** writes **one** AF3 JSON file for the open job, plus an `assets\`
  folder when it references external files.
- **Generate configurations from a file** reads an input list and writes **one
  independent configuration per entry**, each in its own folder with its own
  `assets\`, together with a `manifest.json` run report.

`manifest.json` is a builder-side record. AF3 does not read it.

## Sending results to the inference server

Copy each configuration **with its `assets\` folder**, keeping the layout:

```text
my-job__entry-1\
    my-job__entry-1.json      <-- the AF3 input file
    assets\                   <-- MSAs, templates, custom CCD files
```

The JSON's references are relative, so the folder can be copied on its own; the
builder, the virtual environment and the original input list are not needed. Do
not copy a JSON that still points at files outside its own folder unless you
copy those files with the same relative layout.

## Check the installation at any time

Double-click **`check_dependencies.bat`**: it is read-only, never installs
anything, and prints PASS / MISSING / INCOMPATIBLE / OPTIONAL / WARNING for
each check with an instruction for every failure. See
[`DEPENDENCY_SETUP.md`](DEPENDENCY_SETUP.md) for the status meanings and
recovery steps.

## Moving the application folder

Moving or renaming the folder is allowed, but the editable install records an
absolute path. After a move, run **`setup_windows.bat`** again from the new
location, then **`check_dependencies.bat`**. The launchers themselves always
resolve the folder from their own location, so they need no edit.

## Documentation

- [`RUNNING_THE_APPLICATION.md`](RUNNING_THE_APPLICATION.md) — the two front
  ends, the window's pages, and a first tour.
- [`DEPENDENCY_SETUP.md`](DEPENDENCY_SETUP.md) — setup, dependency statuses,
  troubleshooting and safe recovery.
- [`manual_test_data/af3_builder/README.md`](manual_test_data/af3_builder/README.md)
  — small synthetic inputs and step-by-step walkthroughs.
- [`docs/AF3_BUILDER_INSTALLATION_AND_OUTPUT_AUDIT.md`](docs/AF3_BUILDER_INSTALLATION_AND_OUTPUT_AUDIT.md)
  — the audit behind this layout.
