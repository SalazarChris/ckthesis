"""The interactive JSON builder (the menu UX layer).

One workflow, one screen at a time: open a job (new, or an existing AF3
JSON), edit its job settings and entities, manage its custom CCD and PTM
metadata, save it as JSON with a summary, and derive independent variants
from it. The former session/project management — saved work, recovery,
a separate review workflow, the variant-spec catalogue — was removed with
the rework; the only way to resume a saved job is to open its JSON.

The module owns only menus, prompts, and dispatch. Every state change goes
through the application services (the same calls the e2e suite drives), and
every fixed user-visible sentence is registry wording. Sequence, width, and
encoding rules of the formatting tier (plan §18.8) apply.
"""

from __future__ import annotations

import os

from configbuilder.model import External, Inline
from configbuilder.model.configuration import Pinned, fold_version_selection
from configbuilder.model.records import (
    ComponentRecord,
    FamilyARecord,
    FamilyBRecord,
    FamilyCRecord,
    fold_representation,
)

from configbuilder.app.configuration_service import ReferenceInput
from configbuilder.app.results import FailureReason
from configbuilder.app.status import FieldState
from configbuilder.ui.present.sequence import residue_at
from configbuilder.ui.present.strings import text as _text

__all__ = ["MenuApp", "MINIMUM_WIDTH"]

MINIMUM_WIDTH = 60

# The supported JSON input versions the serializer can emit (plan §10.3:
# the version is always an explicit pin, never inferred).
SUPPORTED_VERSIONS = (1, 2, 3, 4)

# The base's family classification — one place, so listing, counting, and
# the summary agree.
_FAMILY_TYPES = (
    ("protein", FamilyARecord),
    ("rna", FamilyBRecord),
    ("dna", FamilyCRecord),
    ("ligand", ComponentRecord),
)
_FAMILY_OF_TYPE = {type_: family for family, type_ in _FAMILY_TYPES}
_POLYMER_FAMILIES = ("protein", "rna", "dna")
_FAMILY_LABEL_KEYS = {
    "protein": "menu.family_protein",
    "rna": "menu.family_rna",
    "dna": "menu.family_dna",
    "ligand": "menu.family_ligand",
}


# -- pure formatting helpers (text in, text out) --------------------------------


def _rule(width: int) -> str:
    return "=" * max(width, MINIMUM_WIDTH)


def _banner(title: str, width: int) -> str:
    rule = _rule(width)
    padding = max((width - len(title)) // 2, 0)
    return "\n".join([rule, " " * padding + title, rule])


def _records_of_family(configuration, family: str):
    type_ = dict(_FAMILY_TYPES)[family]
    return [r for r in configuration.records if isinstance(r, type_)]


def _version_number(configuration):
    """The pinned JSON version as an int, or ``None`` when unpinned."""
    selection = configuration.format_target.version_selection
    if isinstance(selection, Pinned):
        return selection.version
    return None


def _summary_of(configuration) -> dict:
    """The job's one-screen picture, read only from the model."""
    name = configuration.metadata.name
    selection = configuration.format_target.version_selection
    version = fold_version_selection(
        selection,
        lambda: _text("menu.version_unverified"),
        lambda version: _text("menu.version_pinned") % version,
        lambda evidenced: _text("menu.version_auto"),
    )
    families = {family: _records_of_family(configuration, family)
                for family, _ in _FAMILY_TYPES}
    return {
        "job_name": name,
        "format_version": version,
        "json_version": _version_number(configuration),
        "seed_values": list(configuration.seeds.values),
        "entity_groups": families,
        "entity_count": sum(len(records) for records in families.values()),
    }


# -- the configuration-status view (defaults + what is still required) ----------
#
# One renderer for the status rows ``app`` produces (``app/status.py``): a
# blocked save shows the same picture everywhere, so "what is already valid /
# what is missing / what is optional" reads the same wherever the user looks.

_STATUS_LABEL_ROWS = (
    ("name", "menu.status_name"),
    ("seeds", "menu.status_seeds"),
    ("version", "menu.status_version"),
    ("components", "menu.status_components"),
    ("modifications", "menu.status_modifications"),
    ("msa", "menu.status_msa"),
    ("templates", "menu.status_templates"),
)
_STATUS_LABEL_KEYS = dict(_STATUS_LABEL_ROWS)

# The optional rows: absent is ``NONE``, never a problem and never an error.
_OPTIONAL_KEYS = ("modifications", "msa", "templates")


def _status_label(key: str) -> str:
    return _text(_STATUS_LABEL_KEYS.get(key, "menu.status_other"))


def _provenance(state: str) -> str:
    """The tag that says where a value came from: default or user."""
    if state == FieldState.DEFAULTED:
        return _text("menu.status_automatic")
    return _text("menu.status_provided")


def _version_value(selection) -> str:
    return fold_version_selection(
        selection,
        lambda: _text("menu.version_unverified"),
        lambda version: _text("menu.version_pinned") % version,
        lambda evidenced: _text("menu.version_auto"),
    )


def _entities_value(counts) -> str:
    """The entity row's detail: a per-family count, or "none"."""
    parts = []
    for family in ("protein", "rna", "dna", "ligand"):
        count = counts.get(family, 0) if isinstance(counts, dict) else 0
        if count:
            parts.append("%s %d" % (family, count))
    return ", ".join(parts) if parts else _text("menu.status_none")


def _status_detail(field) -> str:
    """The right-hand half of one status row, from the row's own data."""
    if field.state == FieldState.MISSING:
        return ""
    if field.state == FieldState.INVALID:
        return field.message
    if field.key in _OPTIONAL_KEYS:
        if field.state == FieldState.NONE:
            return _text("menu.status_none")
        if field.state == FieldState.DEFAULTED:
            return "%s %s" % (field.value, _provenance(field.state))
        return str(field.value)
    if field.key == "name":
        return "%s %s" % (field.value, _provenance(field.state))
    if field.key == "seeds":
        rendered = "[%s]" % ", ".join(str(value) for value in field.value)
        return "%s %s" % (rendered, _provenance(field.state))
    if field.key == "version":
        return "%s %s" % (_version_value(field.value), _provenance(field.state))
    if field.key == "components":
        return _entities_value(field.value)
    return str(field.value)


def _status_row(field) -> str:
    """One rendered status row: label, state mark, and detail."""
    mark_key = {
        FieldState.DEFAULTED: "menu.status_ok",
        FieldState.PROVIDED: "menu.status_ok",
        FieldState.NONE: "menu.status_absent",
        FieldState.MISSING: "menu.status_missing",
        FieldState.INVALID: "menu.status_invalid",
    }.get(field.state, "menu.status_absent")
    detail = _status_detail(field)
    return _text("menu.status_line") % (
        _status_label(field.key),
        ("%s  %s" % (_text(mark_key), detail)).strip(),
    )


def _modification_count(record) -> int:
    """How many residue modifications one record carries (ligands: none)."""
    return len(getattr(record, "modifications", None) or ())


def _chain_line(record) -> str:
    """One chain of the job header: the identifier(s), the family, and —
    only when there are any — how many modifications that chain carries."""
    letter = ", ".join(entity.value for entity in record.ids.ids)
    line = _text("menu.job_chain_line") % (
        letter,
        _text(_FAMILY_LABEL_KEYS[_FAMILY_OF_TYPE[type(record)]]),
    )
    count = _modification_count(record)
    if count:
        return line + _text("menu.job_chain_mods") % count
    return line


def _ccd_value(definition) -> str:
    """The custom-CCD row's value: absent, the file, or the inline text's size."""
    if isinstance(definition, External):
        return definition.path.raw
    if isinstance(definition, Inline):
        lines = definition.text.splitlines() or [""]
        return _text("menu.job_header_ccd_inline") % len(lines)
    return _text("menu.job_header_none")


def _job_header_lines(configuration, unsaved: bool = False) -> list:
    """The job menu's header block: what the job is, what is in it, and
    whether the work has been saved.

    Every value is read from the configuration itself — the name, seed
    set, model target, modification count, and custom-CCD source are the
    model's own values, and the chain rows are its records in model order.
    ``unsaved`` is the front end's own last-saved comparison, so it is
    passed in rather than re-derived here. The block is redrawn on every
    visit to the job menu, so it is always the current picture of the work.
    """
    summary = _summary_of(configuration)
    modifications = sum(
        _modification_count(record) for record in configuration.records
    )
    rows = [
        ("menu.job_header_label_name", summary["job_name"]),
        (
            "menu.job_header_label_seed",
            "[%s]" % ", ".join(str(value) for value in summary["seed_values"]),
        ),
        (
            "menu.job_header_label_model",
            _text("menu.job_header_model_value")
            % (
                _text("menu.model_name"),
                _version_value(configuration.format_target.version_selection),
            ),
        ),
        (
            "menu.job_header_label_modifications",
            str(modifications) if modifications else _text("menu.job_header_none"),
        ),
        (
            "menu.job_header_label_ccd",
            _ccd_value(configuration.component_definition),
        ),
        (
            "menu.job_header_label_changes",
            _text("menu.job_header_changes_unsaved")
            if unsaved
            else _text("menu.job_header_none"),
        ),
    ]
    lines = [_text("menu.job_header_row") % (_text(key), value) for key, value in rows]
    lines.append("")
    lines.append(_text("menu.job_header_entities") % summary["entity_count"])
    if configuration.records:
        lines.extend(_chain_line(record) for record in configuration.records)
    else:
        lines.append(_text("menu.entity_list_empty"))
    return lines


def _entity_line(record) -> str:
    """One row of an entity listing: letter(s), family, length or codes."""
    letter = ", ".join(entity.value for entity in record.ids.ids)
    family = _FAMILY_OF_TYPE[type(record)]
    if family == "ligand":
        def _on_code(codes):
            return _text("menu.ligand_by_code") % "+".join(
                code.value for code in codes
            )

        def _on_notation(notation):
            return _text("menu.ligand_by_notation")

        detail = fold_representation(record.representation, _on_code, _on_notation)
        if len(record.ids.ids) > 1:
            return _text("menu.entity_list_ligand_counted") % (
                letter, detail, len(record.ids.ids)
            )
        return _text("menu.entity_list_ligand") % (letter, detail)
    return _text("menu.entity_list_header") % (
        letter,
        family,
        len(record.sequence),
    )


def _mod_rows(record):
    """The residue-numbered modification rows for one record, in the order
    the model stores them. Ligands carry no positions, so they have none."""
    rows = []
    sequence = getattr(record, "sequence", None)
    text = sequence.text if sequence is not None else ""
    for mod in (getattr(record, "modifications", None) or ()):
        residue = residue_at(text, mod.position.value)
        rows.append(
            _text("menu.entity_mod_row")
            % (
                mod.code.value,
                mod.position.value,
                " (%s)" % residue if residue is not None else "",
            )
        )
    return rows


def _say_entity_block(say, record) -> None:
    """One entity row, then its modification rows, if any."""
    say(_entity_line(record))
    for row in _mod_rows(record):
        say(row)


# -- the application object ------------------------------------------------------


class MenuApp:
    """The menu over the application services.

    Construction builds no state and touches no stream; ``run`` drives the
    loop over the console it is given (a real terminal or a scripted one).
    """

    def __init__(self, services, console, width: int = 80) -> None:
        self._services = services
        self._console = console
        self._width = max(width, MINIMUM_WIDTH)
        # The JSON file the current job was last saved to / opened from —
        # offered as the default save destination.
        self._current_path = ""
        # A deep copy of the configuration as of the last save / open / new
        # job. A job is "unsaved" when the live configuration differs from it.
        self._saved_snapshot = None
        # The pristine base configuration while the variant editor is open,
        # and the name the active variant will be saved under.
        self._variant_base = None
        self._variant_name = ""

    # -- primitives ------------------------------------------------------

    def _say(self, line: str = "") -> None:
        self._console.write_line(line)

    def _ask(self, prompt_key: str) -> str:
        return self._console.prompt(_text(prompt_key)).strip()

    def _ask_whole_number(self, prompt_key: str):
        """A positive whole number, asked in the user's own terms.

        Returns the integer, or ``None`` when the user cancelled or typed
        something that is not a positive whole number — in which case the
        reason is said here, in registered wording, instead of a Python
        ``int()`` message reaching the screen (BUG-002).
        """
        raw = self._ask(prompt_key)
        if raw in ("", "0", "q", "back"):
            return None
        if raw.isdigit() and int(raw) >= 1:
            return int(raw)
        self._say(_text("menu.need_whole_number") % raw)
        return None

    def _select(self) -> str:
        return self._console.prompt(_text("menu.select_prompt")).strip().lower()

    def _report(self, outcome) -> bool:
        """Print a service outcome; True when it was applied."""
        if outcome.ok:
            self._say(_text("menu.applied"))
            return True
        self._say(_text("menu.not_applied") % (outcome.message or "refused"))
        return False

    # -- path and file picking -------------------------------------------------

    def _picker_listing(self, directory: str):
        """Sort a directory listing: subdirectories first (names only, the
        ``..`` entry first), then files, both alphabetically. Returns
        ``None`` when the directory cannot be read."""
        try:
            names = sorted(
                os.listdir(directory),
                key=lambda n: (not os.path.isdir(os.path.join(directory, n)), n.lower()),
            )
        except OSError:
            return None
        return [".."] + [n for n in names if not n.startswith(".")]

    def _pick_path(self, prompt_key: str, default: str = "") -> str:
        """Choose an existing file with the keyboard alone: the current
        directory is listed, numbers open directories or select files,
        ``..`` goes up, and anything else typed is taken as a literal path.
        Cancellation is ``0`` or ``q``; an empty answer accepts the
        *default*, when one is offered."""
        directory = os.getcwd()
        while True:
            listing = self._picker_listing(directory)
            if listing is None:
                self._say(_text("menu.pick_cannot_list"))
                directory = os.path.dirname(directory) or os.sep
                continue
            self._say()
            self._say(_text("menu.files_in") % directory)
            for number, name in enumerate(listing, start=1):
                is_dir = (
                    name == ".."
                    or os.path.isdir(os.path.join(directory, name))
                )
                self._say("  %2d) %s%s" % (number, name, "/" if is_dir else ""))
            self._say(_text("menu.pick_hint"))
            raw = self._ask(prompt_key)
            if raw in ("0", "q", "quit", "exit"):
                return ""
            if raw == "":
                return default
            if raw == "..":
                directory = os.path.dirname(directory) or os.sep
                continue
            if raw.isdigit():
                index = int(raw)
                if not 1 <= index <= len(listing):
                    self._say(_text("menu.invalid") % raw)
                    continue
                chosen = os.path.join(directory, listing[index - 1])
                if os.path.isdir(chosen):
                    directory = chosen
                    continue
                return chosen
            return os.path.expanduser(raw)

    def _ask_destination(self, prompt_key: str, default: str) -> str:
        """A save destination typed as a path (not a directory picker): an
        empty answer accepts ``default``. Cancellation is ``0``/``q``."""
        raw = self._console.prompt(_text(prompt_key) % default).strip()
        if raw in ("0", "q", "quit", "exit"):
            return ""
        if not raw:
            return default
        return os.path.expanduser(raw)

    def _project(self):
        project = self._services.projects.project
        if project is None:
            self._say(_text("menu.no_project"))
        return project

    def _records(self, family: str):
        project = self._project()
        if project is None:
            return None
        return _records_of_family(project.configuration, family)

    # -- unsaved-change tracking ------------------------------------------

    def _mark_saved(self) -> None:
        """Record the live configuration as the last-saved one.

        The model is immutable and every mutation derives a new
        ``Configuration``, so holding the object itself is a complete
        snapshot — later edits replace it rather than mutate it.
        """
        project = self._services.projects.project
        self._saved_snapshot = project.configuration if project is not None else None

    def _has_unsaved(self) -> bool:
        project = self._services.projects.project
        if project is None or self._saved_snapshot is None:
            return False
        return project.configuration != self._saved_snapshot

    # -- the run loop ------------------------------------------------------

    def run(self) -> int:
        """The main loop. Status 0 on every deliberate end (exit choice,
        EOF, Ctrl+C) — submenus return, never terminate the process.

        The entry screen is the main menu, which starts a job or opens one.
        A job already in memory (a front end that pre-built one) opens the
        job menu directly; either way, exiting the job returns to the main
        menu.
        """
        try:
            if self._services.projects.is_open:
                self._job_menu()
            self._main_menu()
        except (KeyboardInterrupt, EOFError):
            self._say()
            self._say(_text("menu.interrupted"))
        return 0

    # -- main menu ---------------------------------------------------------

    def _main_menu(self) -> None:
        """The entry screen: start a new job, or open an existing JSON.
        Both lead to the same job menu."""
        while True:
            self._say(_banner(_text("menu.banner_title"), self._width))
            self._say()
            self._say(_text("menu.main_actions"))
            self._say()
            self._say(_text("menu.exit"))
            choice = self._select()
            if choice in ("0", "q", "quit", "exit"):
                return
            if choice == "1":
                self._new_job()
                self._job_menu()
            elif choice == "2":
                if self._open_json_file():
                    self._job_menu()
            elif choice:
                self._say(_text("menu.invalid") % choice)

    def _new_job(self) -> None:
        """Start a fresh job with the standard defaults (name, seeds,
        version pin) and no entities; everything stays editable."""
        name = self._ask("menu.ask_experiment")
        project = self._services.projects.new(name)
        self._current_path = ""
        self._mark_saved()
        self._say(_text("menu.job_created") % project.configuration.metadata.name)

    def _open_json_file(self) -> bool:
        """Load an existing AF3 JSON as the current job. Preview first —
        the current project is untouched until the confirm — and a bad file
        is reported without a traceback. Returns True when a job loaded."""
        path = self._pick_path("menu.ask_import_path")
        if not path:
            return False
        preview = self._services.projects.import_json_preview(path)
        if not preview.ok:
            self._say(_text("menu.import_failed"))
            self._say(_text("menu.import_reason") % (preview.message or "unknown"))
            self._say(_text("menu.import_untouched"))
            return False
        self._say()
        self._say(_text("menu.import_file_line") % path)
        summary = preview.summary
        self._say(_text("menu.summary_name") % summary.get("job_name", ""))
        self._say(_text("menu.import_entities") % summary.get("entity_count", 0))
        for family, count in summary.get("family_counts", {}).items():
            self._say(_text("menu.job_family_header") % family)
            self._say("    x%d" % count)
        self._say(_text("menu.preview_seeds") % (summary.get("seed_values", []),))
        if preview.notes:
            self._say()
            self._say(_text("menu.import_notes"))
            for note in preview.notes:
                self._say(_text("menu.import_note_line") % note.detail)
        entries = [
            (_text("menu.import_yes"), True),
            (_text("menu.import_no"), False),
        ]
        if not self._numbered_choice(_text("menu.import_confirm"), entries, back_note=False):
            return False
        result = self._services.projects.import_json_commit(path)
        if not result.ok:
            self._say(_text("menu.import_failed"))
            self._say(_text("menu.import_reason") % (result.message or "unknown"))
            self._say(_text("menu.import_untouched"))
            return False
        for warning in result.warnings:
            self._say(_text("menu.import_note_line") % warning)
        self._current_path = path
        self._mark_saved()
        self._say(_text("menu.import_loaded"))
        return True

    # -- job menu ----------------------------------------------------------

    def _job_menu(self) -> None:
        """The job screen: the operations that make up building a job."""
        while True:
            project = self._project()
            if project is None:
                return
            self._say(_banner(_text("menu.job_title"), self._width))
            self._say()
            for line in _job_header_lines(
                project.configuration, unsaved=self._has_unsaved()
            ):
                self._say(line)
            self._say()
            self._say(_text("menu.job_actions"))
            self._say()
            self._say(_text("menu.job_back"))
            choice = self._select()
            if choice in ("0", "q", "quit", "exit", "back"):
                if self._leave_job():
                    return
            elif choice == "1":
                self._edit_job_config_menu()
            elif choice == "2":
                self._add_entity_menu()
            elif choice == "3":
                self._edit_entity_menu()
            elif choice == "4":
                self._custom_ccd_menu()
            elif choice == "5":
                self._ptm_menu()
            elif choice == "6":
                self._save_and_summary()
            elif choice == "7":
                self._variant_menu()
            elif choice:
                self._say(_text("menu.invalid") % choice)

    def _leave_job(self) -> bool:
        """Whether leaving the job for the main menu is allowed. Unsaved
        changes are never discarded silently: the user chooses."""
        if not self._has_unsaved():
            return True
        self._say()
        self._say(_text("menu.leave_dirty"))
        entries = [
            (_text("menu.leave_save"), "save"),
            (_text("menu.leave_discard"), "discard"),
            (_text("menu.leave_cancel"), "cancel"),
        ]
        route = self._numbered_choice(
            _text("menu.leave_title"), entries, back_note=False
        )
        if route == "discard":
            return True
        if route == "save":
            return self._save_and_summary()
        return False

    # -- edit job configurations -------------------------------------------

    def _edit_job_config_menu(self) -> None:
        """The job-level settings: name, model seeds, JSON version."""
        configuration = self._services.configuration
        while True:
            if self._project() is None:
                return
            summary = _summary_of(self._services.projects.project.configuration)
            self._say(_banner(_text("menu.builder_title"), self._width))
            self._say()
            self._say(_text("menu.current_settings") % summary["job_name"])
            self._say(_text("menu.current_version") % summary["format_version"])
            self._say(_text("menu.current_seeds") % (summary["seed_values"],))
            self._say()
            self._say(_text("menu.config_actions"))
            self._say()
            self._say(_text("menu.back"))
            choice = self._select()
            if choice in ("0", "q", "back"):
                return
            elif choice == "1":
                name = self._ask("menu.ask_name")
                if name:
                    self._report(configuration.set_name(name))
            elif choice == "2":
                seeds = self._ask("menu.ask_seeds")
                if seeds:
                    self._report(configuration.set_seeds(seeds))
            elif choice == "3":
                self._set_version(configuration)
            elif choice:
                self._say(_text("menu.invalid") % choice)

    def _set_version(self, configuration) -> None:
        """Change the JSON version pin. Only versions the serializer can
        emit are accepted; an existing configuration is never downgraded
        silently to a version that loses a field it already uses."""
        raw = self._ask("menu.ask_version")
        if not raw:
            return
        if not raw.isdigit() or int(raw) not in SUPPORTED_VERSIONS:
            self._say(_text("menu.version_unsupported") % (list(SUPPORTED_VERSIONS),))
            return
        self._report(configuration.set_format_target(version=int(raw)))

    # -- entity selection helpers ------------------------------------------

    def _entity_entries(self, project, families=None):
        """``(label, record key)`` rows for the numbered entity pickers."""
        entries = []
        for record in project.configuration.records:
            family = _FAMILY_OF_TYPE.get(type(record))
            if families is not None and family not in families:
                continue
            entries.append((_entity_line(record).strip(), record.ids.primary.value))
        return entries

    def _select_entity(self, family=None, title=None, empty_note=None):
        """Numbered entity selection → the record key (or ``None``).

        ``family`` restricts the picker to one family, or to a tuple of
        families. ``empty_note`` names the line to say when the picker has
        nothing to offer.
        """
        project = self._project()
        if project is None:
            return None
        if isinstance(family, tuple):
            families = family
        elif family:
            families = (family,)
        else:
            families = None
        entries = self._entity_entries(project, families)
        if not entries and empty_note is not None:
            self._say(_text(empty_note))
            return None
        return self._numbered_choice(title or _text("menu.select_entity"), entries)

    def _record_family(self, record_key: str):
        """The family of the record keyed ``record_key`` (or ``None``)."""
        project = self._services.projects.project
        if project is None:
            return None
        for record in project.configuration.records:
            if record.ids.primary.value == record_key:
                return _FAMILY_OF_TYPE.get(type(record))
        return None

    def _record(self, record_key: str):
        project = self._services.projects.project
        if project is None:
            return None
        for record in project.configuration.records:
            if record.ids.primary.value == record_key:
                return record
        return None

    # -- add entity --------------------------------------------------------

    def _add_entity_menu(self) -> None:
        """Choose an entity type, then run that type's guided input flow."""
        entries = [
            (_text("menu.family_protein"), "protein"),
            (_text("menu.family_dna"), "dna"),
            (_text("menu.family_rna"), "rna"),
            (_text("menu.family_ligand"), "ligand"),
        ]
        family = self._numbered_choice(_text("menu.add_entity_title"), entries)
        if family is None:
            return
        if self._add_entity(family):
            self._say(_text("menu.entity_added"))

    def _ask_quantity(self):
        """How many copies of this component belong in the job? Guided
        choices plus a custom entry."""
        entries = [
            ("1", 1), ("2", 2), ("3", 3), ("5", 5), ("10", 10),
            (_text("menu.quantity_custom"), "custom"),
        ]
        chosen = self._numbered_choice(_text("menu.quantity_menu"), entries)
        if chosen is None:
            return None
        if chosen != "custom":
            return chosen
        while True:
            raw = self._ask("menu.quantity_custom_prompt")
            if raw in ("0", "q", "back"):
                return None
            if raw.strip().isdigit() and int(raw) >= 1:
                return int(raw)
            self._say(_text("menu.quantity_bad_value"))

    def _ligand_kind(self):
        """The CCD-or-SMILES submenu. Returns "ccd", "smiles", or None."""
        entries = [
            (_text("menu.ligand_kind_ccd"), "ccd"),
            (_text("menu.ligand_kind_smiles"), "smiles"),
        ]
        return self._numbered_choice(_text("menu.ligand_kind_menu"), entries)

    def _add_entity(self, family: str) -> bool:
        """The guided add flow for one family. Returns True when a record
        was committed; a cancelled or refused add changes nothing."""
        if family == "ligand":
            kind = self._ligand_kind()
            if kind is None:
                self._say(_text("menu.add_cancelled"))
                return False
            representation = self._ask("menu.add_ligand_value_prompt")
            if not representation:
                self._say(_text("menu.add_cancelled"))
                return False
            copies = self._ask_quantity()
            if copies is None:
                self._say(_text("menu.add_cancelled"))
                return False
            return self._report(
                self._services.configuration.add_record(
                    "ligand", representation=representation,
                    representation_kind=kind, copies=copies,
                )
            )
        prompts = {
            "protein": "menu.add_protein_prompt",
            "rna": "menu.add_rna_prompt",
            "dna": "menu.add_dna_prompt",
        }
        sequence = self._ask(prompts[family])
        if not sequence:
            self._say(_text("menu.add_cancelled"))
            return False
        if not self._report(
            self._services.configuration.add_record(family, sequence)
        ):
            return False
        if family not in ("protein", "rna"):
            return True
        # The record exists now — chain its own questions onto it in one
        # flow (sequence -> MSA y/n -> templates y/n for a protein). Every
        # "no" is legitimate: unset is a normal state, not a gap.
        self._chain_msa(family)
        if family == "protein":
            self._chain_templates(family)
        return True

    def _chain_msa(self, family: str, record_key: str = None) -> None:
        """The record's MSA question: y -> collect, N/blank -> skip."""
        skip = "menu.msa_skip_edit" if record_key is not None else "menu.msa_skip"
        answer = self._ask("menu.ask_msa_yn").lower()
        if answer not in ("y", "yes"):
            self._say(_text(skip))
            return
        if record_key is None:
            records = self._records(family)
            if not records:
                return
            record_key = records[-1].ids.primary.value
        mode = self._collect_msa_mode(family)
        if mode is None:
            return
        if mode in ("automatic", "free"):
            self._report(self._services.configuration.set_alignment(record_key, mode))
            return
        source = self._msa_source_payload()
        if source is None:
            return
        kind, content = source
        if kind == "inline":
            self._report(
                self._services.configuration.set_alignment(
                    record_key, mode, inline_text=content
                )
            )
        else:
            self._report(
                self._services.configuration.set_alignment(
                    record_key, mode, external_path=content
                )
            )

    def _chain_templates(self, family: str, record_key: str = None) -> None:
        """The record's templates question: y -> collect, N/blank -> skip."""
        skip = (
            "menu.templates_skip_edit"
            if record_key is not None
            else "menu.msa_skip"
        )
        answer = self._ask("menu.ask_templates_yn").lower()
        if answer not in ("y", "yes"):
            self._say(_text(skip))
            return
        if record_key is None:
            records = self._records(family)
            if not records:
                return
            record_key = records[-1].ids.primary.value
        self._collect_references_for(record_key)

    def _collect_msa_mode(self, family: str):
        """The numbered MSA-mode menu, filtered to the family's legal
        modes. Returns the service's mode word, or ``None`` to cancel."""
        if family == "protein":
            entries = [
                (_text("menu.msa_mode_auto"), "automatic"),
                (_text("menu.msa_mode_unpaired"), "unpaired"),
                (_text("menu.msa_mode_paired"), "paired"),
                (_text("menu.msa_mode_both"), "both"),
                (_text("menu.msa_mode_free"), "free"),
            ]
        else:
            entries = [
                (_text("menu.msa_mode_auto"), "automatic"),
                (_text("menu.msa_mode_free"), "free"),
                (_text("menu.msa_mode_provided"), "provided"),
            ]
        return self._numbered_choice(_text("menu.msa_mode_menu"), entries)

    def _msa_source_payload(self):
        """Inline paste or file, as an app-layer ``('inline'|'file', text)``
        payload — ``None`` on cancel."""
        entries = [
            (_text("menu.msa_paste_inline"), "inline"),
            (_text("menu.msa_use_file"), "file"),
        ]
        route = self._numbered_choice(_text("menu.msa_source_menu"), entries)
        if route is None:
            return None
        if route == "inline":
            content = self._console.read_multiline(
                _text("menu.msa_inline_header") + "\n"
            ).decode("utf-8", "replace")
            return ("inline", content) if content.strip() else None
        path = self._pick_path("menu.ask_msa_path")
        return ("file", path) if path else None

    def _collect_references_for(self, record_key: str) -> None:
        """The numbered templates menu and dispatch (shared with the edit
        flow); collects the path and index pairs for the explicit-list route."""
        entries = [
            (_text("menu.templates_search"), "search"),
            (_text("menu.templates_none"), "none"),
            (_text("menu.templates_list"), "list"),
        ]
        route = self._numbered_choice(_text("menu.templates_menu"), entries)
        if route is None:
            return
        if route == "search":
            self._report(self._services.configuration.set_references(record_key))
            return
        if route == "none":
            self._report(self._services.configuration.set_references(record_key, references=()))
            return
        external_path = self._pick_path("menu.ask_ref_path") or None
        raw_pairs = self._ask("menu.ask_ref_pairs").strip()
        pairs = []
        if raw_pairs:
            for token in raw_pairs.split(","):
                left, _, right = token.strip().partition(":")
                pairs.append((left.strip(), right.strip()))
        self._report(
            self._services.configuration.set_references(
                record_key,
                references=(
                    ReferenceInput(external_path=external_path, pairs=pairs),
                ),
            )
        )

    # -- edit entity -------------------------------------------------------

    def _edit_entity_menu(self) -> None:
        """List the job's entities, then edit or delete one. The list shows
        the real identifiers and types; an empty job says so."""
        while True:
            project = self._project()
            if project is None:
                return
            if not project.configuration.records:
                self._say(_text("menu.entity_list_empty"))
                self._say(_text("menu.no_entities_edit"))
                return
            entries = self._entity_entries(project)
            record_key = self._numbered_choice(_text("menu.entity_editor_title"), entries)
            if record_key is None:
                return
            self._entity_action_menu(record_key)

    def _entity_action_menu(self, record_key: str) -> None:
        """One selected entity: view it, then Edit or Delete (with confirm)."""
        while True:
            record = self._record(record_key)
            if record is None:
                return
            self._say(_banner(_text("menu.entity_action_title"), self._width))
            self._say()
            self._say(_text("menu.selected_entity") % _entity_line(record).strip())
            for row in _mod_rows(record):
                self._say("  " + row.strip())
            self._say()
            polymer = _FAMILY_OF_TYPE.get(type(record)) in _POLYMER_FAMILIES
            self._say(
                _text(
                    "menu.entity_actions_polymer"
                    if polymer
                    else "menu.entity_actions"
                )
            )
            self._say()
            self._say(_text("menu.back"))
            choice = self._select()
            if choice in ("0", "q", "back"):
                return
            if choice == "1":
                self._edit_entity_fields(record_key)
            elif choice == "2":
                if self._delete_entity_key(record_key):
                    return
            elif choice == "3" and polymer:
                self._record_mod_menu(record_key)
            elif choice:
                self._say(_text("menu.invalid") % choice)

    def _edit_entity_fields(self, record_key: str) -> None:
        """The record's own fields, and only its own. A polymer is asked for
        its sequence and description plus the alignment/template questions
        its family supports; a ligand is asked for its representation.
        Blank answers keep the current values."""
        family = self._record_family(record_key)
        if family is None:
            return
        if family == "ligand":
            kind = self._ligand_kind()
            if kind is None:
                return
            value = self._ask("menu.add_ligand_value_prompt")
            if not value:
                return
            if kind == "smiles":
                self._report(
                    self._services.configuration.set_representation(
                        record_key, notation=value
                    )
                )
            else:
                self._report(
                    self._services.configuration.set_representation(
                        record_key, codes=value.replace(",", " ").split()
                    )
                )
            return
        sequence = self._ask("menu.edit_sequence_prompt")
        description = self._ask("menu.edit_desc_prompt")
        if sequence or description:
            self._report(
                self._services.configuration.update_record(
                    record_key,
                    sequence=sequence or None,
                    description=description or None,
                )
            )
        if family in ("protein", "rna"):
            self._chain_msa(family, record_key)
        if family == "protein":
            self._chain_templates(family, record_key)

    def _delete_entity_key(self, record_key: str) -> bool:
        """Delete one entity after confirmation. Returns True when it was
        removed (the caller then returns to the entity list)."""
        entries = [
            (_text("menu.delete_yes"), True),
            (_text("menu.delete_no"), False),
        ]
        confirmed = self._numbered_choice(
            _text("menu.delete_confirm") % record_key, entries, back_note=False
        )
        if not confirmed:
            return False
        if self._report(self._services.configuration.remove_record(record_key)):
            self._say(_text("menu.removed") % record_key)
            return True
        return False

    def _record_mod_menu(self, record_key: str) -> None:
        """The selected polymer's own modifications: view, add, edit or
        remove. The same collection, validation and refusal paths as PTM
        management, scoped to the record the user picked."""
        while True:
            record = self._record(record_key)
            if record is None:
                return
            self._say(_banner(_text("menu.mod_menu_title"), self._width))
            self._say()
            self._say(_text("menu.selected_entity") % _entity_line(record).strip())
            for row in _mod_rows(record):
                self._say("  " + row.strip())
            self._say()
            self._say(_text("menu.mod_actions"))
            self._say()
            self._say(_text("menu.back"))
            choice = self._select()
            if choice in ("0", "q", "back"):
                return
            if choice == "1":
                self._add_modification_to(record_key)
            elif choice == "2":
                self._edit_modification_on(record_key)
            elif choice == "3":
                self._remove_modification_on(record_key)
            elif choice:
                self._say(_text("menu.invalid") % choice)

    # -- custom CCD management ---------------------------------------------

    def _custom_ccd_menu(self) -> None:
        """The job's custom component (userCCD) definition: view, add, edit,
        or remove. A job carries at most one — the AF3 schema has one
        ``userCCD`` / ``userCCDPath`` field — presented here as a list of
        zero or one with the definition's content shown."""
        while True:
            project = self._project()
            if project is None:
                return
            definition = project.configuration.component_definition
            self._say(_banner(_text("menu.ccd_title"), self._width))
            self._say()
            self._say_ccd_definition(definition)
            self._say()
            self._say(_text("menu.ccd_actions"))
            self._say()
            self._say(_text("menu.back"))
            choice = self._select()
            if choice in ("0", "q", "back"):
                return
            if choice == "1":
                self._say()
                self._say_ccd_definition(definition)
            elif choice == "2":
                self._add_ccd_definition()
            elif choice == "3":
                self._add_ccd_definition()
            elif choice == "4":
                self._remove_ccd_definition()
            elif choice:
                self._say(_text("menu.invalid") % choice)

    def _say_ccd_definition(self, definition) -> None:
        if definition is None:
            self._say(_text("menu.ccd_none"))
            return
        self._say(_text("menu.ccd_current"))
        if isinstance(definition, External):
            self._say(_text("menu.ccd_path") % definition.path.raw)
            return
        if isinstance(definition, Inline):
            lines = definition.text.splitlines() or [""]
            self._say(_text("menu.ccd_inline") % lines[0])
            self._say(_text("menu.ccd_inline_lines") % len(lines))
            return
        self._say(_text("menu.ccd_none"))

    def _add_ccd_definition(self) -> None:
        """Collect a custom CCD definition — inline CIF text or an external
        file path — and set it on the job."""
        entries = [
            (_text("menu.msa_paste_inline"), "inline"),
            (_text("menu.msa_use_file"), "file"),
        ]
        route = self._numbered_choice(_text("menu.ccd_source_menu"), entries)
        if route is None:
            return
        if route == "inline":
            content = self._console.read_multiline(
                _text("menu.paste_definition") + "\n"
            ).decode("utf-8", "replace")
            if not content.strip():
                self._say(_text("menu.save_cancelled"))
                return
            outcome = self._services.configuration.set_component_definition(
                inline_text=content
            )
        else:
            path = self._pick_path("menu.ask_ccd_path")
            if not path:
                self._say(_text("menu.save_cancelled"))
                return
            outcome = self._services.configuration.set_component_definition(
                external_path=path
            )
        if self._report(outcome):
            self._say(_text("menu.ccd_set"))

    def _remove_ccd_definition(self) -> None:
        project = self._project()
        if project is None:
            return
        if project.configuration.component_definition is None:
            self._say(_text("menu.ccd_none"))
            return
        entries = [
            (_text("menu.delete_yes"), True),
            (_text("menu.delete_no"), False),
        ]
        confirmed = self._numbered_choice(
            _text("menu.ccd_confirm"), entries, back_note=False
        )
        if not confirmed:
            return
        if self._report(self._services.configuration.clear_component_definition()):
            self._say(_text("menu.ccd_removed"))

    # -- PTM management ----------------------------------------------------

    def _ptm_menu(self) -> None:
        """Post-translational modifications on the job's polymer chains:
        view, add, edit, or remove. Every operation reuses the same
        validation and serialization the base workflow uses."""
        while True:
            if self._project() is None:
                return
            self._say(_banner(_text("menu.ptm_title"), self._width))
            self._say()
            self._say_ptm_list()
            self._say()
            self._say(_text("menu.ptm_actions"))
            self._say()
            self._say(_text("menu.back"))
            choice = self._select()
            if choice in ("0", "q", "back"):
                return
            if choice == "1":
                self._say()
                self._say_ptm_list()
            elif choice == "2":
                self._ptm_add()
            elif choice == "3":
                self._ptm_edit()
            elif choice == "4":
                self._ptm_remove()
            elif choice:
                self._say(_text("menu.invalid") % choice)

    def _protein_records(self):
        project = self._project()
        if project is None:
            return []
        return [
            record
            for record in project.configuration.records
            if _FAMILY_OF_TYPE.get(type(record)) in _POLYMER_FAMILIES
        ]

    def _say_ptm_list(self) -> None:
        records = [r for r in self._protein_records() if getattr(r, "modifications", None)]
        if not records:
            self._say(_text("menu.ptm_none"))
            return
        for record in records:
            self._say(_text("menu.ptm_record") % _entity_line(record).strip())
            for row in _mod_rows(record):
                self._say(row)

    def _select_modification(self, record):
        """Numbered pick over one record's modifications → the 0-based index,
        or ``None``."""
        modifications = tuple(getattr(record, "modifications", ()) or ())
        if not modifications:
            self._say(_text("menu.no_mods_on_record"))
            return None
        entries = [
            ("%s @ %d" % (mod.code.value, mod.position.value), index)
            for index, mod in enumerate(modifications)
        ]
        return self._numbered_choice(_text("menu.mod_remove_prompt"), entries)

    def _select_modification_target(self):
        """The PTM menu's carrier picker: a polymer record key, or ``None``."""
        return self._select_entity(
            family=_POLYMER_FAMILIES,
            title=_text("menu.mod_target_entity"),
            empty_note="menu.no_modification_target",
        )

    def _add_modification_to(self, record_key: str) -> None:
        """Collect a code and position and add them to one known record."""
        code = self._ask("menu.ask_code")
        if not code:
            self._say(_text("menu.mod_cancelled"))
            return
        position = self._ask_whole_number("menu.ask_position")
        if position is None:
            self._say(_text("menu.mod_cancelled"))
            return
        if self._report(
            self._services.configuration.add_modification(record_key, code, position)
        ):
            self._say(_text("menu.modification_added"))

    def _edit_modification_on(self, record_key: str) -> None:
        """Pick one of the record's own modifications and change it."""
        record = self._record(record_key)
        if record is None:
            return
        index = self._select_modification(record)
        if index is None:
            return
        code = self._ask("menu.ptm_edit_code_prompt")
        position = self._ask("menu.ptm_edit_position_prompt")
        new_position = None
        if position:
            if not position.isdigit() or int(position) < 1:
                self._say(_text("menu.need_whole_number") % position)
                return
            new_position = int(position)
        if not code and new_position is None:
            self._say(_text("menu.mod_cancelled"))
            return
        if self._report(
            self._services.configuration.update_modification(
                record_key, index, code=code or None, position=new_position
            )
        ):
            self._say(_text("menu.ptm_updated"))

    def _remove_modification_on(self, record_key: str) -> None:
        """Pick one of the record's own modifications and remove it."""
        record = self._record(record_key)
        if record is None:
            return
        index = self._select_modification(record)
        if index is None:
            return
        if self._report(
            self._services.configuration.remove_modification(record_key, index)
        ):
            self._say(_text("menu.modification_removed"))

    def _ptm_add(self) -> None:
        record_key = self._select_modification_target()
        if record_key is None:
            return
        self._add_modification_to(record_key)

    def _ptm_edit(self) -> None:
        record_key = self._select_modification_target()
        if record_key is None:
            return
        self._edit_modification_on(record_key)

    def _ptm_remove(self) -> None:
        record_key = self._select_modification_target()
        if record_key is None:
            return
        self._remove_modification_on(record_key)

    # -- save and summary --------------------------------------------------

    def _say_summary(self, configuration) -> None:
        """The job's summary: the model's own counts, never a re-derivation."""
        summary = _summary_of(configuration)
        version = summary["json_version"]
        self._say(_banner(_text("menu.summary_title"), self._width))
        self._say()
        self._say(_text("menu.summary_name") % summary["job_name"])
        self._say(_text("menu.summary_seeds") % (summary["seed_values"],))
        self._say(
            _text("menu.summary_version")
            % (version if version is not None else summary["format_version"])
        )
        self._say(_text("menu.summary_entities") % summary["entity_count"])
        self._say()
        self._say(_text("menu.summary_breakdown"))
        groups = summary["entity_groups"]
        self._say(_text("menu.summary_protein") % len(groups["protein"]))
        self._say(_text("menu.summary_dna") % len(groups["dna"]))
        self._say(_text("menu.summary_rna") % len(groups["rna"]))
        self._say(_text("menu.summary_ligand") % len(groups["ligand"]))
        self._say(_text("menu.summary_other") % 0)
        if configuration.records:
            self._say()
            for record in configuration.records:
                _say_entity_block(self._say, record)
        self._say()
        self._say(_rule(self._width))

    def _suggest_file_name(self, configuration) -> str:
        name = (configuration.metadata.name or "job").strip() or "job"
        return name.replace(" ", "_") + ".json"

    def _save_and_summary(self) -> bool:
        """Show the summary, ask where to save, then validate, serialize and
        write. Returns True on a successful save; a failed validation or
        write leaves the job editable and intact."""
        project = self._project()
        if project is None:
            return False
        self._say_summary(project.configuration)
        default = self._current_path or self._suggest_file_name(project.configuration)
        destination = self._ask_destination("menu.ask_save_path", default)
        if not destination:
            self._say(_text("menu.save_cancelled"))
            return False
        overwrite = os.path.exists(destination)
        if overwrite:
            entries = [
                (_text("menu.overwrite_yes"), True),
                (_text("menu.overwrite_no"), False),
            ]
            if not self._numbered_choice(
                _text("menu.overwrite_confirm") % destination, entries, back_note=False
            ):
                self._say(_text("menu.save_cancelled"))
                return False
        if not self._write_json(destination, name=None, overwrite=overwrite):
            return False
        self._current_path = destination
        self._mark_saved()
        return True

    def _write_json(self, destination: str, name, overwrite: bool) -> bool:
        """Validate, serialize and write the current configuration through
        the generation service. Nothing is written before the plan succeeds;
        a failed write keeps the in-memory job intact."""
        from configbuilder.ui.present import format_findings

        plan = self._services.generation.plan_save(
            destination, name=name, overwrite=overwrite
        )
        if not plan.ok:
            if plan.failure_reason == FailureReason.VALIDATION_BLOCKED:
                self._say(_text("menu.save_job_blocked"))
                status = self._services.validation.status()
                if status is not None:
                    self._say_status(status)
                self._print_cards(plan.findings, format_findings)
            else:
                self._say(_text("menu.not_applied") % (plan.message or ""))
            for conflict in plan.conflicts:
                self._say(_text("menu.export_conflict") % conflict)
            return False
        result = self._services.generation.execute(plan)
        if result.ok:
            for path in result.written:
                self._say(_text("menu.save_job_wrote") % path)
            for path in result.skipped:
                self._say(_text("menu.export_skipped") % path)
            return True
        for error in result.errors:
            self._say(_text("menu.not_applied") % error)
        return False

    # -- variants ----------------------------------------------------------

    def _variant_menu(self) -> None:
        """Variant management over the current job. The base is snapshotted
        on entry; the user edits the live copy and saves it as its own JSON,
        then the working copy is reset to the base. The base is never
        mutated, and no variant inherits an earlier one's changes."""
        project = self._project()
        if project is None:
            return
        # Immutability makes the base object a complete, isolated snapshot:
        # the variant edits replace the project's configuration with new
        # objects and never touch this one.
        self._variant_base = project.configuration
        self._variant_name = ""
        try:
            while True:
                project = self._project()
                if project is None:
                    return
                self._say(_banner(_text("menu.variant_title"), self._width))
                self._say()
                self._say(_text("menu.variant_base_job") % self._variant_base.metadata.name)
                self._say(
                    _text("menu.variant_base_entities")
                    % len(self._variant_base.records)
                )
                self._say(
                    _text("menu.variant_current")
                    % (self._variant_name or self._default_variant_name())
                )
                self._say()
                self._say(_text("menu.variant_actions"))
                self._say()
                self._say(_text("menu.back"))
                choice = self._select()
                if choice in ("0", "q", "back"):
                    return
                if choice == "1":
                    self._set_variant_name()
                elif choice == "2":
                    self._add_entity_menu()
                elif choice == "3":
                    self._edit_entity_menu()
                elif choice == "4":
                    self._save_variant_and_reset()
                elif choice:
                    self._say(_text("menu.invalid") % choice)
        finally:
            # Leaving variant management restores the base and forgets the
            # active variant entirely — the base job is never modified.
            self._reset_variant()
            self._variant_base = None

    def _default_variant_name(self) -> str:
        base = self._variant_base.metadata.name if self._variant_base is not None else "job"
        return "%s_variant" % base

    def _set_variant_name(self) -> None:
        current = self._variant_name or self._default_variant_name()
        raw = self._ask("menu.variant_name_prompt")
        if raw:
            self._variant_name = raw
            self._say(_text("menu.variant_named") % raw)
        else:
            self._say(_text("menu.variant_named") % current)

    def _save_variant_and_reset(self) -> None:
        """Save the active variant as its own file, then reset to the base.
        A failed validation or write resets nothing and loses nothing."""
        default = self._variant_name or self._default_variant_name()
        destination = self._ask_destination(
            "menu.ask_variant_path", default + ".json"
        )
        if not destination:
            self._say(_text("menu.save_cancelled"))
            return
        overwrite = os.path.exists(destination)
        if overwrite:
            entries = [
                (_text("menu.overwrite_yes"), True),
                (_text("menu.overwrite_no"), False),
            ]
            if not self._numbered_choice(
                _text("menu.overwrite_confirm") % destination, entries, back_note=False
            ):
                self._say(_text("menu.save_cancelled"))
                return
        name = self._variant_name or self._default_variant_name()
        if not self._write_json(destination, name=name, overwrite=overwrite):
            return
        self._say(_text("menu.variant_saved") % destination)
        self._reset_variant()
        self._say(_text("menu.variant_reset"))

    def _reset_variant(self) -> None:
        """Restore the pristine base configuration and clear the variant's
        name, ready for the next variant. The base snapshot is retained so
        the next variant starts from the same base again."""
        self._variant_name = ""
        if self._variant_base is None:
            return
        project = self._services.projects.project
        if project is not None:
            self._services.projects._replace_project(
                project.with_configuration(self._variant_base)
            )

    # -- view helpers ------------------------------------------------------

    def _say_status(self, status) -> None:
        """The status block: every field, its state, and the verdict."""
        self._say(_banner(_text("menu.status_title"), self._width))
        self._say()
        for field in status.fields:
            self._say(_status_row(field))
        self._say()
        self._say(
            _text("menu.status_ready" if status.ready else "menu.status_incomplete")
        )

    def _print_cards(self, findings, format_findings) -> None:
        """Findings as the numbered cards the present layer produces."""
        for card in format_findings(findings, width=self._width):
            self._say(
                _text("menu.card_line")
                % (card.number, card.severity_line, card.context)
            )
            for line in card.lines:
                self._say(_text("menu.finding_indent") + line)

    # -- numbered-choice machinery -----------------------------------------

    def _numbered_choice(self, title, entries, back_note=True):
        """Show a numbered list and return the chosen item (or ``None``
        for back/cancel/EOF). ``entries`` are ``(label, payload)`` pairs;
        the payload never reaches the screen."""
        if title:
            self._say(_banner(title, self._width))
            self._say()
        if not entries:
            return None
        for index, (label, _) in enumerate(entries, start=1):
            self._say(_text("menu.choice_line") % (index, label))
        if back_note:
            self._say()
            self._say(_text("menu.back"))
        # Re-ask in a loop, never by recursing: an input stream that never
        # produces a valid choice would otherwise grow the stack on every
        # keystroke (BUG-009).
        while True:
            choice = self._select()
            if choice in ("0", "q", "back", ""):
                return None
            if choice.isdigit() and 1 <= int(choice) <= len(entries):
                return entries[int(choice) - 1][1]
            self._say(_text("menu.invalid") % choice)
            for index, (label, _) in enumerate(entries, start=1):
                self._say(_text("menu.choice_line") % (index, label))
            if back_note:
                self._say()
                self._say(_text("menu.back"))
