# AF3 Configuration Builder — Workflow Fix Implementation Report

**Source audit:** [`AF3_BUILDER_COMPLETE_WORKFLOW_AUDIT.md`](AF3_BUILDER_COMPLETE_WORKFLOW_AUDIT.md)
(the *as-found* record, left unedited apart from a status pointer).
**Scope:** the approved F-items only. F-04 and F-11 were explicitly rejected and are not
implemented.

---

## 1. What was fixed, by item

### F-01 — the window can create a single-stranded DNA record

The service already accepted `duplex=False`; only the window always asked for a duplex.

- `SequenceFormDialog` (`dialogs/entity_forms.py`) gained an optional two-radio group
  (`gui.dna_duplex_choice`, `gui.dna_duplex_pair`, `gui.dna_duplex_single`) that exists
  **only** for DNA: `duplex=None` deselects the feature entirely, so protein and RNA forms
  are unchanged. Its answer is returned through `apply(sequence, description, duplex)`.
- `EntitiesPage._add_sequence` passes `duplex=(True if family == "dna" else None)` and
  forwards the answer to `GuiState.add_record(..., duplex=...)`, which now takes
  `duplex=True` by default and hands it straight to
  `ConfigurationService.add_record`. The Edit path ignores the answer
  (`_duplex`), because editing a strand's text must not silently add or remove a partner.
- Default behaviour is unchanged: an accepted DNA dialog commits the duplex, exactly as
  before.

### F-05 — deletion confirmations name what is actually removed

New module `configbuilder/ui/present/notices.py` holds one `removal_notice(identifiers,
partner_key, copy_count)` function. Both front ends call it, so the same deletion cannot be
described two ways, and neither re-implements the rule:

- a duplex partner → `gui.delete_duplex` names the strand **and** the partner;
- a multi-copy ligand → `gui.delete_copies` names every identifier and the count;
- otherwise → `gui.delete_single`.

The console also reports the service's own result message (`menu.removed_detail`) rather
than assuming the deletion succeeded silently.

### F-10 — covalent bonds are now manageable from the console

The job menu (still option `8`, so no existing numbering moved) opens
**Covalent bond management**: list the job's linkages with both endpoints rendered as
`entity, residue N, atom`, add one, or remove one by the number the list showed.

- `_add_bond` / `_collect_bond_endpoint` collect two `(entity, 1-based residue, atom)`
  endpoints and call `ConfigurationService.add_linkage(...)`.
- `_remove_bond` calls `ConfigurationService.remove_linkage(index)`.
- No validation, ordering or endpoint rule is duplicated: the service's own refusal is
  printed through the existing `_report` path, which is why an out-of-range residue or a
  SMILES ligand endpoint is refused with the service's wording.

Verified against a real save: a protein `A` plus an `ATP` ligand `B` with a bond
`A:1:SG`–`B:1:C1` writes

```json
"bondedAtomPairs": [[["A", 1, "SG"], ["B", 1, "C1"]]]
```

### F-02 — `both` mode can carry two independent alignment sources

- `AlignmentFormDialog` (`dialogs/advanced_forms.py`) now shows a **paired side** block
  only for `both` mode, with its own radio route (`gui.alignment_paired_same` /
  `inline` / `file`). "Same as the unpaired source" is the default, which is the service's
  own single-source rule, so a `both` job with one source reopens and saves exactly as
  before.
- `GuiState.set_alignment` forwards `paired_inline_text` / `paired_external_path`;
  `AdvancedPage._apply_alignment` sends each side's own kind.
- `advanced.alignment_state` now returns `(mode, kind, text, paired_kind, paired_text)`;
  the paired pair is `("", "")` whenever the paired side is the unpaired source, so the
  form reopens with both sources intact instead of collapsing them.

### F-03 — inline mmCIF templates can be authored, imported and preserved

- `advanced._reference_row` returns `(kind, value, pairs)` where `kind` is `file` or
  `inline`, read from the model (`External` → its path, `Inline` → its text). The template
  table's first column (`gui.templates_col_file`) therefore shows what the row actually is.
- `_apply_references` sends `ReferenceInput(external_path=…)` for a file row and
  `ReferenceInput(inline_text=…)` for an inline row — never both, because the two are
  mutually exclusive.
- The reference dialog lets each row be edited as a path or as pasted text, so an imported
  inline template is shown, edited and re-sent as inline; accepting the dialog unchanged
  never converts it into a path.
- The console gained the same capability: each template asks for its source once
  (`menu.templates_source_title`), and answering *paste* collects the mmCIF through
  `read_multiline` and sends `ReferenceInput(inline_text=…)`.

### F-06 — one custom-CCD action instead of a duplicated Add/Edit

The console's Custom CCD menu is now **view / set-or-replace / remove**. There is no
separate "edit" that asked the identical questions and pre-filled nothing: the job holds at
most one `userCCD`/`userCCDPath`, so replacing *is* the edit. The GUI's three-state
none/inline/file editor already pre-loaded the existing definition and is unchanged.

### F-08 — ligand descriptions in the console

The console asks for an optional description when adding a ligand
(`menu.ask_entity_description`) and offers to change it on edit, passing it through the
same `description` parameter the service already validated. The three presence states are
preserved: an unchanged description is passed as `None` so an unset description stays unset
and an explicitly empty one stays explicitly empty.

### F-09 — inline MSA text in the console

Both alignment sides accept a multiline paste (`read_multiline`, the infrastructure the
custom-CCD editor already used) as an alternative to a file: `inline_text` for the unpaired
side, `paired_inline_text` for the paired side. File-based flows are untouched, and an empty
paste changes nothing (`menu.msa_inline_empty`).

### F-15 — the batch policy is visible before writing

`batch_preview_note()` (shared, in `present/strings.py`) now states three things the audit
found under-explained:

- what an entry becomes and that the base job is untouched;
- that the overwrite policy's default refuses the whole batch if **one** different existing
  file is found, and that choosing another folder is the safe recovery;
- that copied external files (MSA, templates, `userCCDPath`) travel beside each
  configuration (`batch.preview_assets`).

The overwrite and path-policy radios also carry per-choice hint strings
(`gui.policy_overwrite_*_hint`, `gui.policy_path_*_hint`). No workflow was redesigned.

### F-12 — the legacy `generate_from_file` API is documented, not deleted

`VariantService.generate_from_file` keeps its behaviour and now carries an explicit
**LEGACY / DEPRECATED — do not add callers** contract in its docstring, naming the current
workflow (`GenerationService.generate_input_batch`) and its distinct semantics (it commits
`base + AddRecord` specs into the open job; the current one writes independent files and
never touches the base). The verified caller inventory and the migration plan are in
[`LEGACY_GENERATION_API_MIGRATION.md`](LEGACY_GENERATION_API_MIGRATION.md). Removal is
deferred until fixture generation and the AF3 validator scenario are migrated and verified,
so nothing in the fixture or validation tooling breaks today.

### F-07 — `set_job_description` removed

`ConfigurationService.set_job_description` is gone. A job-level description is **not** part
of the AF3 wire format (only the per-entity `description` is), no front end ever offered
it, and no output could carry its result — an unreachable setter is a trap for the next
caller. `ConfigurationMetadata.description` stays, because the configuration value carries
it; only the setter was dead. The AF3 validator's "descriptions" scenario
(`tools/af3_validation/run_all.py`) now covers the four per-entity descriptions, with a
comment saying why.

### F-13 — the dead variant modules: nothing to move

The instruction was to move `pages/variants.py` and `dialogs/variant_forms.py` into a
legacy location rather than delete them. By the time this work started they had already
been removed in commit `a4a488c` ("Make the ligand-file workflow the variant service…"),
and a repository-wide search finds no importer, no reference and no runtime import of
either module. There is therefore nothing to relocate and no dangling reference to clean
up; recreating them as legacy files would re-add code that nothing uses. Recorded here
rather than silently skipped.

### F-04 / F-11 — not implemented

JSON preview surfacing (F-04) and save-review-before-write (F-11) were rejected. The hidden
`PreviewPage` / `GenerationService.show_json` implementation is untouched, and the save
workflow still writes without an added review step.

---

## 2. Tests and actual results

New coverage:

- `tests/unit/ui/test_console_parity.py` (new, 12 tests) drives the real `MenuApp` through
  the real services and reads the saved JSON: add/view/remove a covalent bond, a bond
  needs two entities, a ligand description on add and on edit, inline unpaired MSA, an
  inline paired side kept apart from the unpaired one, an inline template written as
  `mmcif` (not a path), one source question per template, a duplex strand's deletion naming
  its partner, a multi-copy ligand's deletion naming every identifier, and the CCD menu
  having no duplicate edit.
- `tests/gui/test_entity_management.py`: a single strand from the DNA form; only DNA offers
  the duplex choice.
- `tests/gui/test_advanced_settings.py`: each side of `both` gets its own source; `both`
  without a paired choice reuses the unpaired source; the form reopens with both sources;
  the paired controls appear only for `both`; an inline template can be authored in the
  window; accepting the dialog does not turn an inline template into a path; a row keeps its
  own kind.
- Existing suites updated where the workflow changed (console template/MSA transcripts, the
  CCD menu, the job menu, entity lifecycle, validator scenario).

Runs executed here (each exited 0; no failures, no errors):

| Run | Tests passed |
| --- | --- |
| `tests/variant tests/contract tests/serialization tests/negative tests/golden` | 79 |
| `tests/unit/ui tests/unit/app` | 334 |
| `tests/gui/test_advanced_settings.py tests/gui/test_entity_management.py` | 110 |
| `tests/e2e/test_menu_acceptance.py tests/e2e/test_entity_lifecycle.py tests/e2e/test_template_cli_subprocess.py` | 53 |
| `tests/e2e/test_manual_test_data.py tests/gui/test_generate_output.py` | 47 |

Beyond assertions, one console job was built end to end and its file inspected: the saved
JSON contained `bondedAtomPairs: [[["A", 1, "SG"], ["B", 1, "C1"]]]` with a protein and a
ligand record, i.e. the bond reached the wire format rather than an internal object.

**Not run:** the complete `tests/gui` directory in one invocation exceeded the available
time budget (killed at 560 s, no failing test observed before the cutoff), so the GUI
suites were run as the two files this change touches instead. That is a coverage limit, not
a pass.

---

## 3. Files changed

Source:

- `configbuilder/app/configuration_service.py` — `set_job_description` removed (F-07).
- `configbuilder/app/variant_service.py` — legacy/deprecation contract on
  `generate_from_file` (F-12).
- `configbuilder/ui/present/notices.py` *(new)* — the shared removal wording (F-05).
- `configbuilder/ui/present/strings.py` — the new registry entries (all F-items).
- `configbuilder/ui/render/menus.py` — bonds (F-10), inline MSA (F-09), ligand
  descriptions (F-08), one CCD action (F-06), shared delete notice (F-05), inline template
  source (F-03).
- `configbuilder/ui/render/qt/state.py` — `add_record(duplex=…)`, `set_alignment` paired
  sources.
- `configbuilder/ui/render/qt/dialogs/entity_forms.py` — DNA duplex radios (F-01).
- `configbuilder/ui/render/qt/dialogs/advanced_forms.py` — paired MSA block (F-02),
  per-row template kind (F-03).
- `configbuilder/ui/render/qt/pages/advanced.py` — alignment 5-tuple, per-kind
  `ReferenceInput` (F-02, F-03).
- `configbuilder/ui/render/qt/pages/entities.py` — duplex answer forwarded, shared delete
  notice (F-01, F-05).
- `tools/af3_validation/run_all.py` — scenario no longer calls the removed setter (F-07).

Tests: `tests/unit/ui/test_console_parity.py` *(new)*, `tests/unit/ui/test_menu.py`,
`tests/unit/ui/test_msa_flow.py`, `tests/unit/ui/test_template_flow.py`,
`tests/unit/ui/test_audit_regressions.py`, `tests/unit/variants/test_quantity_series.py`,
`tests/gui/test_advanced_settings.py`, `tests/gui/test_entity_management.py`,
`tests/e2e/test_menu_acceptance.py`, `tests/e2e/test_entity_lifecycle.py`,
`tests/e2e/test_manual_test_data.py`, `tests/e2e/test_template_cli_subprocess.py`.

Documentation: this report, `docs/LEGACY_GENERATION_API_MIGRATION.md` *(new)*, and the
status pointer added to the audit.

---

## 4. Remaining limitations

1. **The console cannot edit an existing bond**, only add and remove. Endpoints are
   collected fresh; changing one is a remove plus an add. That matches the service, which
   has `add_linkage`/`remove_linkage` and no update operation.
2. **A single-stranded DNA record is a model state the window can now create**, but the
   batch reader still constructs a duplex per DNA input line — the documented batch
   behaviour, deliberately unchanged.
3. **Inline templates are validated the same way as path templates** (the shared reference
   rules), but an inline template has no file for the copy step, so nothing travels beside
   the JSON: it is embedded in the configuration. That is the AF3 contract and the reason
   inline is preferable for portability.
4. **`VariantService.generate_from_file` still exists** with its job-mutating semantics
   until the fixture and validator callers are migrated (F-12, deferred by instruction).
5. **No Windows execution** was needed for this task: every change is in shared Python code
   exercised on this machine's interpreter.
6. **The GUI was exercised through its test harness**, not by hand on a desktop; the Qt
   widgets were driven programmatically.

---

## 5. Git

Commits are grouped in two: the implementation with its tests, and the documentation. A
per-issue split was not practical in a green tree because every F-item adds entries to one
shared string registry (`ui/present/strings.py`) whose meta-test fails on a dead entry — so
any commit that lands the registry without all of its consumers is red.

Unrelated working-tree material was left untouched and uncommitted: the untracked thesis
drafts and images, scratch probes (`1`, `test.json`, `Untitled_job_1.json`,
`vg_probe.txt`), `docs/screenshots/`, `docs/ui_referene/`, and the pre-existing deletions of
the `docs/AF3_GUI_*_PROMPT.md` planning documents.
