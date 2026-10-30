# Legacy generation API — status and migration plan

`VariantService.generate_from_file` (`configbuilder/app/variant_service.py`) is a
**legacy, deprecated** surface. It is kept for now because fixture and test tooling
still calls it. It is **not** the user-facing batch workflow.

## Why it is not the workflow

| | `VariantService.generate_from_file` | `GenerationService.generate_input_batch` |
| --- | --- | --- |
| What it produces | `base + AddRecord` variant specs **committed into the open project** | one independent AF3 JSON file per input entry, plus a manifest |
| Effect on the open job | mutated (the base gains a spec per entry) | unchanged |
| Called by the console / window | no | yes (menu option 7, Entities ▸ *Generate configurations from file…*) |
| Preview | `inspect_batch_file` (read-only) | `inspect_input_file` (read-only), same wording |
| Output policies | n/a (nothing is written) | overwrite + path policy, applied by the shared planner |

The two share the reading (`persistence`), the per-entry spec construction
(`app.batch_variants`) and the result counters (`app.results.batch_counts`), so a
migration changes the *commit target*, not the parsing.

## Current callers (verified by search)

- `tests/unit/app/test_batch_variants.py` — the method's own unit coverage.
- `tests/e2e/test_app_pipeline.py` — one pipeline scenario.
- `tests/e2e/test_manual_test_data.py` — manual-test-data scenarios.
- `tests/fixtures/af3_pipeline/generate_fixtures.py` — fixture generation.
- `tools/af3_validation/run_all.py` — the AF3 validator's "batch variants" scenario.

No module under `configbuilder/ui` calls it.

## Migration plan

1. **Add a file-writing equivalent to the fixture tooling.** `generate_fixtures.py`
   needs the *files*, not specs in a project, so it can call
   `GenerationService.generate_input_batch` with an explicit output directory per
   fixture case.
2. **Convert `tools/af3_validation/run_all.py`.** Its scenario asserts that the batch
   route works end to end; pointing it at `generate_input_batch` keeps that assertion
   and drops the project mutation.
3. **Convert the unit tests** to the same service, asserting the written files and the
   `BatchCounts` roles (configurations, manifests, assets) instead of committed specs.
4. **Move the remaining e2e scenarios** to the file-based route; where a scenario
   exists only to prove *spec commitment*, keep it against `add_spec` directly, which
   is the primitive `generate_from_file` composes.
5. **Delete `generate_from_file`, `inspect_batch_file` and the commit-based helpers**
   once steps 1–4 pass. The behaviour still required by the validator and fixtures is
   the reading, the spec construction and the counts — all of which stay.

Until step 5, the method's docstring carries the `LEGACY / DEPRECATED` marker so a
maintainer cannot mistake it for the shipped workflow.
