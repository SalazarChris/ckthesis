# CONTRACT_PIN — observed input-format evidence

This file records **dated observations of which input format the deployment accepts**
(IMPLEMENTATION_PLAN.md §2.2, §22.4). It is **provenance documentation only**: the
running application never reads, locates, or parses it. When a version is pinned,
the operator cites the record below (its `Pin ID`, e.g. `PIN-001`) as the
`evidence` of `Pinned` in the configuration's `FormatTarget` — the citation
travels in the model, not through this file.

Field-level rules come exclusively from `AUTHORITATIVE_SPEC.md` and live in
`configbuilder/validation/catalogue.py`. The two kinds of evidence are never mixed.

Until a version has been verified against the deployment and pinned with its
evidence reference, `VersionSelection` is `Unverified`: a CONTRACT rule reports
an `ERROR` and generation is blocked (plan §10.3) while every other phase proceeds
normally.

## Record structure (plan §22.4)

Each accepted observation is one record:

| Field | Content |
|---|---|
| Pin ID | Stable identifier, e.g. `PIN-001`, referenced by manifests and tests. |
| Observed input format | The dialect and the version value carried by the accepted input. This becomes the pinned target. |
| Evidence source | What was submitted and through which execution path; the probe input is retained as `fixtures/golden/external/`. |
| Date tested | The date the observation was made. |
| Execution outcome | Whether acceptance was confirmed through the real path, and how far the run proceeded. |
| Unknown deployment metadata | Explicitly listed: internal software release identity; installation metadata; any other accepted format versions. Recorded as **unknown**, never as a guess. |
| Supplementary evidence | Any version string the deployment volunteers through its normal user-facing interface or job output. Informational; does not become a pin. |

## Records

**No accepted observation has been recorded yet.**

**Status: no evidence recorded (documentation status only).** The runtime does not read
this file; until an operator pins a version and cites an observation here as its
`evidence`, configurations remain `Unverified` and generation is blocked by design
(plan §10.3). The probe procedure is a human task described in plan §22.4: hand-write a
minimal valid input, submit it through the deployment's normal execution path, observe
acceptance, add the record here, and pin the version with this record's Pin ID as its
evidence reference.

## Unknown deployment metadata (standing)

- Internal software release identity: **unknown** (plan §22.1 Q1 — not required, not a blocker).
- Installation metadata: **unknown**.
- Other accepted input formats/versions: **unknown**.

## Re-probe triggers

The pin is a dated observation of a system that can be upgraded without notice. Re-establish
the record when: the deployment is known or suspected to have changed; an input the builder
generated is rejected; or a feature is needed that the pinned version does not cover
(plan §22.4).
