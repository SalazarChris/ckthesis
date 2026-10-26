# UI text audit — verifying the wording document against the code

The pasted wording review (ambiguous phrases, glossary, capitalization, default
filenames, MSA labels, verification checklist) was checked line by line against
this repository before anything was changed. Its patch table could not be
applied as written: **none of its 16 "original" strings exist in this codebase**
(grep over `configbuilder/` and `tests/` returned zero matches for every one of
them), and every location was marked *unspecified*. The document appears to
have been written against an imagined application.

The corrected mapping — every recommendation against the real string registry
keys, with its decision — is in
[UI_TEXT_AUDIT_AND_PATCH.csv](UI_TEXT_AUDIT_AND_PATCH.csv).

## Where the wording lives

All user-facing text is centralized: the wizard/console/desktop strings in
[configbuilder/ui/present/strings.py](../configbuilder/ui/present/strings.py)
(~870 registry entries), domain labels in
`configbuilder/model/traceability.py`, and validation wording in the rule
messages under `configbuilder/validation/`. A meta-test
(`tests/unit/ui/test_string_registry.py`) asserts that no user-visible string
lives outside those sources. ~59 test files assert exact wording.

## Applied (7 strings, all in `configbuilder/ui/present/strings.py`)

| Key | Line | Before → After | Why |
|---|---|---|---|
| `menu.msa_choice_title` | 170 | `MSA configuration:` → `MSA (multiple sequence alignment) configuration:` | The acronym was never expanded anywhere (doc §2). |
| `menu.msa_choice_default` | 171 | `Use the current/default MSA behavior` → `Keep the current MSA setting` | The real-world instance of the doc's vague phrase; now matches its sibling `menu.msa_keep_edit`. |
| `menu.msa_keep_new` | 174 | `Default MSA behavior: …` → `Automatic MSA: AlphaFold searches for the MSA at inference time; …` | Same vague "default … behavior" construction; also removes the only two American-spelling `behavior` occurrences in user-facing text. |
| `gui.alignment_hint` | 618 | `Choose how this chain's alignment is supplied.` → `Choose how this entity's multiple sequence alignment (MSA) is supplied.` | MSA is stored per sequence entry, shared by all copies — and `gui.alignment_dialog` in the *same dialog* already said "entity". |
| `gui.alignment_hint_free` | 622 | `No alignment data: this chain is folded without one.` → `No alignment data: prediction runs without an MSA.` | Same chain/entity mix; the new phrasing states the consequence directly. |
| `gui.variant_hint_sequence` | 799 | `Replace one chain's sequence…` → `Replace one entity's sequence in this variant only.` | A sequence change targets one record; with `id: ["B","F"]` all copies share it, so "chain" was wrong. |
| `gui.variant_hint_remove_modification` | 805 | `…from this variant's expanded chain.` → `…from this variant only.` | "Expanded chain" was internal implementation jargon in a user hint. |
| `gui.variant_hint_alignment` | 808 | `one protein or RNA chain's alignment` → `one protein or RNA entity's alignment` | Alignment is configured per entity. |

No test asserted any of the replaced strings (verified by grep before editing);
the string-registry meta-test passes afterwards.

## Deliberately kept (see CSV for full rationale)

* **`menu.job_chain_line` = `Chain %s %s`** — the line enumerates the record's
  chain identifiers; the model's own domain label for `EntityId` is **"Chain
  identifier"** (`model/traceability.py:67`). This is the specific context the
  proposed glossary allows, and four assertions in `tests/unit/ui/test_menu.py`
  depend on it. (The section above it already reads "Entities (n):".)
* **`Add an RNA chain` / `Edit the selected RNA chain`** — molecule descriptors
  parallel to `Add a protein`, `Add a DNA duplex`, `Edit the selected DNA
  strand`; "chain" is correct for a polymer and distinguishes RNA from the
  duplex case.
* **Overwrite / cancel / readiness / blocked strings** — already clearer than
  the document's originals: `%s already exists. Overwrite it?`,
  `Replace an existing file`, `Cancel`, `Ready — nothing blocks generation.`,
  `Not ready: %d blocking findings.`
* **MSA option labels** — the doc's alternatives are factually wrong for this
  app: *"(unpaired sequence only)"* conflates no-MSA with unpaired-only, and
  *"Compute new MSA (ignore existing)"* promises a builder-side computation
  that does not exist (AlphaFold searches at inference time).
* **Template label** — the file filter accepts mmCIF only; adding "PDB" would
  advertise an unsupported format.

## Deferred decisions (explicitly not done)

1. **Title Case for every button and menu.** The current style is deliberate
   and grouped: action labels carrying a family name are Title Case
   (`Add Protein`, `Add RNA`), controls are sentence case (`Validate all`,
   `Select all`, `Create a variant…`). Applying the proposal means rewriting a
   large share of ~870 strings and the exact-text assertions in ~59 test files.
   Needs its own go/no-go.
2. **The `protein_2ligand.json` default-filename scheme.** Output naming is
   job-name → slug (`multi-ligand-small-protein/`) with deterministic variant
   file names; the user elected to keep it. The proposed algorithm is recorded
   in the CSV for later.
3. **Not applicable to this project:** `.af3json` extension, `--save-json`
   flag (the CLI is menu-driven), Qt `.ui` files (widgets are built in Python),
   `pytest-qt` (GUI tests use the project's own PySide6 conftest).

## Verification checklist results

| Check | Command | Result |
|---|---|---|
| No obsolete phrase from the doc exists in the code | `grep -rF` over `configbuilder/` + `tests/` for all 16 originals | 0 matches for every one |
| Button/menu labels carry no trailing period | audit of 774 single-line registry entries | Pass (`gui.bond_*` hits are status sentences, not buttons) |
| Messages carry terminal punctuation | same audit | Pass (remaining no-period entries are deliberate fragments: `none`, `MISSING`, `Select all`) |
| Applied strings come from the registry | `python -m pytest tests/unit/ui/test_string_registry.py -o addopts="" -q` | 5 passed |
| Assertion updates for the changed strings | `python -m pytest tests/unit/ui/test_menu.py tests/unit/ui/test_msa_flow.py tests/unit/ui/test_numbered_flows.py tests/unit/ui/test_string_registry.py -o addopts="" -q` | 41 passed |
| Full core suite (after all edits) | `python -m pytest -o addopts="" -q --ignore=tests/gui` | **1147 passed, 1 skipped**, exit 0 |
| GUI suite (offscreen Qt, after all edits) | `QT_QPA_PLATFORM=offscreen python -m pytest tests/gui -p no:cacheprovider --basetemp=.pytest-tmp -o addopts="" -q` | **306 passed**, exit 0 |
| Compile + lint (changed files) | `python -m compileall -q configbuilder`; `ruff check --select E4,E7,E9,F <changed>` | clean |

Five assertions in three test files referenced the old literals
(`"MSA configuration:"` ×5, `"AlphaFold will search for the MSA at inference
-time"` ×1). They were **updated to the new wording**, not loosened — including
the one `not in` assertion, which would otherwise have passed trivially.
`tests/unit/ui/test_menu.py` also had a pre-existing unused `import re`, removed
while that file was already being edited.
