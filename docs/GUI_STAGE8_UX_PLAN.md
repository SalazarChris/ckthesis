# Stage 8 — UX Simplification Plan (before implementation)

Three problems were reported after a real launch of the Stage 7 GUI:

1. job-wide settings live in two places (Overview and a separate Job Settings tab);
2. Generate & Output exposes every option at once, so the basic workflow is hard to see;
3. Variants & Batch uses internal vocabulary and does not say which of its workflows to pick.

This plan is the information architecture the implementation follows. Every change is a
view-layer change: the services, the AF3 wire format, validation, identifier allocation,
variant expansion, batch atomicity and output policies are untouched.

## Baseline (measured before any edit)

| Suite | Command | Result |
| --- | --- | --- |
| GUI (offscreen) | `QT_QPA_PLATFORM=offscreen .venv-gui/Scripts/python.exe -m pytest -o addopts="" -q tests/gui` | 227 passed |
| Architecture + launchers + string registry | `python -m pytest -o addopts="" -q tests/architecture tests/unit/test_launchers.py tests/unit/ui/test_string_registry.py` | 64 passed |
| Services (app + variants + output) | `python -m pytest -o addopts="" -q tests/unit/app tests/unit/variants tests/unit/output` | 224 passed |
| Full suite | `python -m pytest -o addopts="" -q tests` | recorded in the implementation report |

Working tree: 30 tracked files modified, 70 untracked paths (all user work). No reset,
clean, stash, checkout, revert or commit is performed by this stage.

## Target navigation

```
Overview          job settings (name · seeds · version) · summary · readiness · findings
Entities          entity table + the selected entity's own settings (Details / Advanced)
Variants & Batch  create: one variant | a series | from a file · list · selected variant
Generate & Output 1 what · 2 where · 3 review · 4 generate · warnings, conflicts, result
JSON Preview      generated JSON (read-only)
```

The Job Settings top-level tab is removed. Overview already hosts the same
`JobSettingsPanel` instance (Stage 7), so there is exactly one service-backed editor and
one destination; the panel keeps its default/changed markers and its Apply-per-row
behaviour.

## Workstream A — Overview owns job-wide settings

- Delete the Job Settings tab and the `JobSettingsPage` wrapper; `JobSettingsPanel` stays.
- `MainWindow.settings_page` becomes a documented alias of `OverviewPage.job_settings`, so
  the existing lifecycle/advanced tests keep exercising the same widget.
- Overview groups, in order: **Job settings** panel, **Job summary** (dialect, entity
  count, readiness verdict beside the service's readiness rows), **Validation findings**
  (compact table + detail line). One scroll surface; tables lose their oversized minimums.
- Refused edits keep restoring the service's values and surfacing its message (unchanged
  behaviour; a test pins it).

## Workstream B — Variants & Batch

One workspace, three labelled creation paths in a tab strip at the top of the page, each
with a one-sentence explanation:

| Path | Label | Sentence (plain language) |
| --- | --- | --- |
| one variant | `Create a variant` | make one alternative configuration from the base job by choosing a supported change |
| quantity series | `Create a series` | repeat a supported parameter over a range; the plan shows every variant before anything is created |
| file batch | `Create variants from a file` | one variant per line of a sequence/SMILES file; the parsed entries are shown before the batch is committed |

Below: the variants list (with the secondary actions — Add change, Rename, Duplicate,
Remove, Validate — beside it), then the selected variant's declared changes, validation
state and JSON. Primary action per path stays the path's own button; nothing else competes.

No new service call, no second variant engine, no direct model edit. Cancellation in every
path leaves the base and the variant collection untouched (already the service behaviour;
a Stage 8 test pins it per path).

## Workstream C — Generate & Output

A four-step layout, top to bottom, with the always-visible warnings pane:

1. **What do you want to generate?** — base job only / selected variant / all variants,
   with a sentence explaining what each writes (one file and no manifest, versus a file per
   variant plus manifest). Only the service's own scopes are offered.
2. **Where should the files go?** — folder picker, the effective folder shown, and the two
   policies behind an **Advanced options** disclosure. The disclosure starts collapsed; its
   header states that the defaults are safe, and no destructive policy is ever chosen
   silently. Hints explain overwrite/skip/stop and path handling in the policies' own
   vocabulary.
3. **Review the plan** — *Preview plan* plans through `GenerationService` and shows the
   plan's files, assets and copied paths. Conflict and warning panes are **outside** the
   disclosure and show before the user can commit.
4. **Generate files** — confirmation dialog naming destination and policies, re-plan and
   compare, then the reviewed plan's own `execute`. Result pane reports written / skipped /
   copied / refused per item, with copy-path available for both files and assets.

Save JSON (File menu / toolbar) keeps writing one file and is not routed through this page.

## Workstream D — Consistency

- One shared `CollapsibleSection` component (arrow header + body) in the Qt render layer,
  used by the Advanced-options disclosure; it reuses the central `style.py` sheet.
- Step headings use the existing `heading_label`/`hint_label` roles; no new style framework.
- Every reachable control keeps an accessible name or an associated label; empty states,
  stale-plan states and refusals keep their current service-derived wording.
- Long content stays inspectable: scroll areas on Overview, no fixed-height squeeze on the
  plan/conflict panes, monospace JSON previews unchanged.

## Tests

Updated: the top-level tab list (no Job Settings), the Stage 7 "two placements" test
(now one placement, still one source of truth), and the string registry (the removed tab
label is deleted rather than left dead).

Added — `tests/gui/test_stage8_ux.py`:

1. no Job Settings tab; Overview exposes name/seeds/version and applies them through the
   services;
2. an accepted Overview change refreshes the service-backed views, a refused one restores
   the service values and reports;
3. the Variants page shows three clearly labelled creation paths and every previously
   supported operation is still reachable;
4. cancelling each of the three paths changes neither the base nor the specs;
5. series and batch previews report the planned/parsed counts and any problem before commit;
6. editing a variant leaves the base configuration object unchanged;
7. Generate & Output follows select → destination → review → confirm → result;
8. a cancelled generation and a refused plan write nothing;
9. conflicts stay visible while the advanced disclosure is collapsed;
10. an asset path can still be selected and copied.

## Manual Windows checklist (for the user, after the automated pass)

- Overview contains the job settings once and is not overwhelmingly dense.
- Create one variant, preview it, cancel once, then commit another.
- Create a quantity series and confirm the planned count before creating it.
- Import a small batch file and confirm malformed input is visible before commit.
- Preview output, inspect conflicts, cancel, and confirm no files were written.
- Generate into a temporary folder and inspect the JSON, assets and manifest.
- Readability at default size, maximized, and Windows 125 % / 150 % scaling.

None of these manual items are claimed as verified by this stage; the offscreen suite is
the only UI verification performed.
