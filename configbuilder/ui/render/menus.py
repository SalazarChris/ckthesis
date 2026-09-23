"""The free-navigation interactive builder (the menu UX layer).

The guided wizard walks a fixed step order; this layer lets the user enter
any section at any time over **one experiment**: a base configuration, then
variants as first-class named views on top of it, then an explicit export.
It owns only menus, prompts, and dispatch — every state change goes
through the application services (the same calls the e2e suite drives),
and every fixed user-visible sentence is registry wording. Sequence,
width, and encoding rules of the formatting tier (plan §18.8) apply:
layout is computed for the console's measured width with 80 as the
documented minimum; below that the banner/rule widths degrade but no
content is ever cut.
"""

from __future__ import annotations

from configbuilder.model.configuration import fold_version_selection
from configbuilder.model.records import (
    ComponentRecord,
    FamilyARecord,
    FamilyBRecord,
    FamilyCRecord,
    fold_representation,
)
import os

from configbuilder.app.configuration_service import ReferenceInput
from configbuilder.ui.present.strings import text as _text

__all__ = ["MenuApp", "MINIMUM_WIDTH"]

MINIMUM_WIDTH = 60

# The base's family classification — one place, so listing, counting, and
# the summary agree.
_FAMILY_TYPES = (
    ("protein", FamilyARecord),
    ("rna", FamilyBRecord),
    ("dna", FamilyCRecord),
    ("ligand", ComponentRecord),
)
_FAMILY_OF_TYPE = {type_: family for family, type_ in _FAMILY_TYPES}


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


def _summary_of(configuration) -> dict:
    """The base's one-screen summary, read only from the model."""
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
        "seed_values": list(configuration.seeds.values),
        "entity_groups": families,
        "entity_count": sum(len(records) for records in families.values()),
    }


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


# -- the application object ------------------------------------------------------


class MenuApp:
    """The free-navigation builder over the five application services.

    Construction builds no state and touches no stream; ``run`` drives
    the loop over the console it is given (a real terminal or a scripted
    one — the same seam the wizard uses).
    """

    def __init__(self, services, console, width: int = 80) -> None:
        self._services = services
        self._console = console
        self._width = max(width, MINIMUM_WIDTH)
        self._output_dir = "output"

    # -- primitives ------------------------------------------------------

    def _say(self, line: str = "") -> None:
        self._console.write_line(line)

    def _ask(self, prompt_key: str) -> str:
        return self._console.prompt(_text(prompt_key)).strip()

    def _select(self) -> str:
        return self._console.prompt(_text("menu.select_prompt")).strip().lower()

    def _confirm(self) -> bool:
        return self._ask("menu.ask_confirm").lower() in ("y", "yes")

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
        """Choose a path with the keyboard alone: the current directory is
        listed, numbers open directories or select files, ``..`` goes up,
        and anything else typed is taken as a literal path — so pasting a
        full path still works. Cancellation is ``0`` or ``q``; an empty
        answer accepts the *default*, when one is offered — the service
        layer remains the authority on whether the path exists or is
        usable."""
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
            # Anything else is a literal path — verbatim, no existence
            # gate here: the service layer owns whether a path exists or
            # is usable, and abstract paths are legitimate input.
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

    # -- the run loop ------------------------------------------------------

    def run(self) -> int:
        """The master loop. Status 0 on every deliberate end (exit choice,
        EOF, Ctrl+C) — submenus return, never terminate the process."""
        try:
            self._master_menu()
        except (KeyboardInterrupt, EOFError):
            self._say()
            self._say(_text("menu.interrupted"))
        return 0

    # -- master menu -------------------------------------------------------

    def _master_menu(self) -> None:
        while True:
            project = self._services.projects.project
            if project is None:
                self._new_or_load()
                if self._services.projects.project is None:
                    return  # EOF or a declined start: leave the application
            project = self._services.projects.project
            summary = _summary_of(project.configuration)
            self._say(_banner(_text("menu.banner_title"), self._width))
            self._say()
            self._say(_text("menu.current") % summary["job_name"])
            self._say(_text("menu.entities") % summary["entity_count"])
            self._say(_text("menu.seeds") % (summary["seed_values"],))
            self._say(_text("menu.variants") % len(project.specs))
            self._say()
            self._say(_text("menu.master_actions"))
            self._say()
            self._say(_text("menu.exit"))
            choice = self._select()
            if choice in ("0", "q", "quit", "exit"):
                return
            elif choice == "1":
                self._job_builder_menu()
            elif choice == "2":
                self._validation()
            elif choice == "3":
                self._show_json()
            elif choice == "4":
                self._save_project()
            elif choice == "5":
                self._load_project()
            elif choice == "6":
                self._variants_menu()
            elif choice == "7":
                self._export_menu()
            elif choice == "8":
                self._wizard()
            elif choice == "9":
                self._summary_screen()
            elif choice:
                self._say(_text("menu.invalid") % choice)

    def _new_or_load(self) -> None:
        self._say(_banner(_text("menu.banner_title"), self._width))
        self._say()
        self._say(_text("menu.start_actions"))
        self._say()
        self._say(_text("menu.exit"))
        choice = self._select()
        if choice == "1":
            name = self._ask("menu.ask_experiment")
            self._services.projects.new(name or "experiment")
        elif choice == "2":
            self._load_project()
        elif choice == "3":
            self._import_json()
        # anything else (blank, unknown, EOF) declines and lets the caller exit

    def _import_json(self) -> None:
        """Load an existing AF3 JSON as the current job (§7 of the import
        feature). Preview first — the current project is untouched until
        the numbered confirm — then unsupported-field notes get an
        explicit continue/cancel choice."""
        path = self._pick_path("menu.ask_import_path")
        if not path:
            return
        preview = self._services.projects.import_json_preview(path)
        if not preview.ok:
            self._say(_text("menu.import_failed"))
            self._say(_text("menu.import_reason") % (preview.message or "unknown"))
            self._say(_text("menu.import_untouched"))
            return
        self._say()
        self._say(_text("menu.import_file_line") % path)
        summary = preview.summary
        self._say(_text("menu.preview_name") % summary.get("job_name", ""))
        self._say(_text("menu.base_entities") % summary.get("entity_count", 0))
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
        proceed = self._numbered_choice(_text("menu.import_confirm"), entries, back_note=False)
        if not proceed:
            return
        result = self._services.projects.import_json_commit(path)
        if not result.ok:
            self._say(_text("menu.import_failed"))
            self._say(_text("menu.import_reason") % (result.message or "unknown"))
            self._say(_text("menu.import_untouched"))
            return
        for warning in result.warnings:
            self._say(_text("menu.import_note_line") % warning)
        self._say(_text("menu.import_loaded"))

    def _save_project(self) -> None:
        """Save = write the current job as AF3 JSON in the output
        destination, through the generation pipeline. The .cbproj working
        copy is maintained automatically in the internal directory; no
        project-file path is ever asked for."""
        self._generate_base_json()

    def _load_project(self) -> None:
        """Open saved work: restore the internal working copy — no file
        listing, no path choice. JSON files enter through Import."""
        result = self._services.projects.load_saved_work()
        if result.ok:
            self._say(_text("menu.open_saved_loaded"))
        else:
            self._say(_text("menu.open_saved_none"))

    def _wizard(self) -> None:
        """The existing guided front end, kept as a compatibility path."""
        from configbuilder.ui.render.wizard import run_wizard

        run_wizard(self._services, console=self._console)

    # -- job builder (the free-navigation core) ----------------------------

    def _job_builder_menu(self) -> None:
        while True:
            self._say(_banner(_text("menu.builder_title"), self._width))
            self._say()
            self._say(_text("menu.builder_actions"))
            self._say()
            self._say(_text("menu.back"))
            choice = self._select()
            if choice in ("0", "q", "back"):
                return
            elif choice == "1":
                self._job_settings()
            elif choice == "2":
                self._entity_menu("protein")
            elif choice == "3":
                self._entity_menu("rna")
            elif choice == "4":
                self._entity_menu("dna")
            elif choice == "5":
                self._entity_menu("ligand")
            elif choice == "6":
                self._bonded_pairs()
            elif choice == "7":
                self._custom_ccd()
            elif choice == "8":
                self._delete_entity()
            elif choice == "9":
                self._summary_screen()
            elif choice:
                self._say(_text("menu.invalid") % choice)

    # -- job settings --------------------------------------------------------

    def _job_settings(self) -> None:
        configuration = self._services.configuration
        while True:
            if self._project() is None:
                return
            summary = _summary_of(self._services.projects.project.configuration)
            self._say(_banner(_text("menu.settings_title"), self._width))
            self._say()
            self._say(_text("menu.current_settings") % summary["job_name"])
            self._say(_text("menu.current_version") % summary["format_version"])
            self._say(_text("menu.current_seeds") % (summary["seed_values"],))
            self._say()
            self._say(_text("menu.settings_actions"))
            self._say()
            self._say(_text("menu.back"))
            choice = self._select()
            if choice in ("0", "q", "back"):
                return
            elif choice == "1":
                self._report(configuration.set_name(self._ask("menu.ask_name")))
            elif choice == "2":
                self._set_version(configuration)
            elif choice == "3":
                self._report(configuration.set_seeds(self._ask("menu.ask_seeds")))
            elif choice == "4":
                self._generate_seeds(configuration)
            elif choice:
                self._say(_text("menu.invalid") % choice)

    def _set_version(self, configuration) -> None:
        raw = self._ask("menu.ask_version")
        if not raw:
            self._report(configuration.unset_format_target())
            return
        self._report(configuration.set_format_target(version=raw))

    def _generate_seeds(self, configuration) -> None:
        """Generate seeds through the service — a count in, the service's
        own deterministic set out. No randomness is invented here."""
        raw = self._ask("menu.ask_count")
        if not raw.isdigit():
            self._say(_text("menu.invalid") % raw)
            return
        seeds = list(range(1, int(raw) + 1))
        if self._report(configuration.set_seeds(seeds)):
            self._say(_text("menu.seeds_generated") % (seeds,))

    # -- entity categories ---------------------------------------------------

    def _entity_menu(self, family: str) -> None:
        titles = {
            "protein": _text("menu.proteins_title"),
            "rna": _text("menu.rna_title"),
            "dna": _text("menu.dna_title"),
            "ligand": _text("menu.ligands_title"),
        }
        while True:
            records = self._records(family)
            if records is None:
                return
            self._say(_banner(titles[family], self._width))
            self._say()
            self._say(_text("menu.currently") % (len(records), family))
            self._say()
            for record in records:
                self._say(_entity_line(record))
            if not records:
                self._say(_text("menu.entity_list_empty"))
            self._say()
            self._say(_text("menu.entity_actions"))
            if family in ("protein", "rna"):
                self._say()
                self._say(_text("menu.entity_actions_extra"))
            self._say()
            self._say(_text("menu.back"))
            choice = self._select()
            if choice in ("0", "q", "back"):
                return
            elif choice == "1":
                self._add_entity(family)
            elif choice == "2":
                self._edit_entity()
            elif choice == "3":
                self._delete_entity()
            elif choice == "4":
                records = self._records(family)
                if records is None:
                    return
                for record in records:
                    self._say(_entity_line(record))
            elif choice == "5":
                self._msa_menu(family)
            elif choice:
                self._say(_text("menu.invalid") % choice)

    def _ask_quantity(self):
        """How many copies of this component belong in the job? Guided
        choices plus a custom entry — pure base-job quantity, nothing
        about variants or series here."""
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
            self._say(_text("menu.series_bad_value"))

    def _ligand_kind(self):
        """The CCD-or-SMILES submenu. Returns "ccd", "smiles", or None
        to cancel — one shared wording source for every ligand input."""
        entries = [
            (_text("menu.ligand_kind_ccd"), "ccd"),
            (_text("menu.ligand_kind_smiles"), "smiles"),
        ]
        return self._numbered_choice(_text("menu.ligand_kind_menu"), entries)

    def _add_entity(self, family: str) -> None:
        prompts = {
            "protein": "menu.add_protein_prompt",
            "rna": "menu.add_rna_prompt",
            "dna": "menu.add_dna_prompt",
            "ligand": "menu.add_ligand_prompt",
        }
        if family == "ligand":
            kind = self._ligand_kind()
            if kind is None:
                return
            representation = self._ask(prompts[family])
            copies = self._ask_quantity()
            if copies is None:
                return
            self._report(
                self._services.configuration.add_record(
                    "ligand", representation=representation,
                    representation_kind=kind, copies=copies,
                )
            )
            return
        if not self._report(
            self._services.configuration.add_record(
                family, self._ask(prompts[family])
            )
        ):
            return
        if family not in ("protein", "rna"):
            return
        # The record exists now — chain the alignment/template questions
        # onto it in one flow (sequence -> MSA y/n -> templates y/n). Every
        # "no" is legitimate: unset is a normal state, not a gap.
        self._chain_msa(family)
        self._chain_templates(family)

    def _chain_msa(self, family: str) -> None:
        """The add-flow MSA question: y -> collect, N/blank -> skip."""
        answer = self._ask("menu.ask_msa_yn").lower()
        if answer not in ("y", "yes"):
            self._say(_text("menu.msa_skip"))
            return
        configuration = self._services.configuration
        records = self._records(family)
        record_key = records[-1].ids.ids[0].value if records else ""
        mode = self._msa_mode(family)
        if mode in ("automatic", "free"):
            self._report(configuration.set_alignment(record_key, mode))
            return
        inline_text, external_path = self._msa_source()
        self._report(
            configuration.set_alignment(
                record_key, mode, inline_text=inline_text, external_path=external_path
            )
        )


    def _chain_templates(self, family: str) -> None:
        """The add-flow templates question: y -> collect, N/blank -> skip."""
        answer = self._ask("menu.ask_templates_yn").lower()
        if answer not in ("y", "yes"):
            self._say(_text("menu.msa_skip"))
            return
        records = self._records(family)
        record_key = records[-1].ids.ids[0].value if records else ""
        self._references_for(record_key)

    def _msa_mode(self, family: str) -> str:
        """The mode answer, translated to the service's vocabulary.

        Single letters (the fast path in the chained prompt) and full
        words (power users, existing scripts) both resolve. An
        unrecognized answer is reported and asked again — never silently
        guessed; a blank line (or EOF) takes ``automatic``.
        """
        prompt = (
            "menu.ask_msa_mode_yn"
            if family == "protein"
            else "menu.ask_rna_mode_yn"
        )
        while True:
            raw = self._ask(prompt).lower()
            if family == "protein":
                table = {
                    "p": "paired", "paired": "paired",
                    "u": "unpaired", "unpaired": "unpaired",
                    "b": "both", "both": "both",
                    "a": "automatic", "automatic": "automatic",
                    "f": "free", "free": "free", "none": "free",
                }
            else:
                table = {
                    "a": "automatic", "automatic": "automatic",
                    "f": "free", "free": "free", "none": "free",
                    "p": "provided", "provided": "provided",
                }
            if raw in table:
                return table[raw]
            if raw in ("", "automatic"):
                return "automatic"
            self._say(_text("menu.invalid") % raw)

    def _edit_entity(self) -> None:
        configuration = self._services.configuration
        record_key = self._ask("menu.ask_record")
        sequence = self._ask("menu.ask_sequence")
        description = self._ask("menu.ask_description")
        self._report(
            configuration.update_record(
                record_key,
                sequence=sequence or None,
                description=description,
            )
        )

    def _delete_entity(self) -> None:
        record_key = self._select_entity(title=_text("menu.delete_entity_title"))
        if record_key is None:
            return
        self._report(self._services.configuration.remove_record(record_key))

    # -- MSA / structural templates (§15 set_alignment / set_references) ------

    def _msa_menu(self, family: str) -> None:
        """Alignments and templates live on *existing* records: this menu
        only collects the mode, the source, and the index pairs. Every
        change goes through the application services — the UI never
        touches alignment objects or wire fields."""
        configuration = self._services.configuration
        if family not in ("protein", "rna"):
            self._say(_text("menu.msa_note"))
            return
        while True:
            if self._project() is None:
                return
            self._say(_banner(_text("menu.msa_title"), self._width))
            self._say()
            self._say(_text("menu.msa_note"))
            self._say()
            self._say(
                _text("menu.msa_actions")
                if family == "protein"
                else _text("menu.msa_actions_rna")
            )
            self._say()
            self._say(_text("menu.back"))
            choice = self._select()
            if choice in ("0", "q", "back"):
                return
            elif choice == "1" and family == "protein":
                self._set_protein_alignment(configuration)
            elif choice == "2" and family == "protein":
                self._set_references(configuration)
            elif choice == "1" and family == "rna":
                self._set_rna_alignment(configuration)
            elif choice:
                self._say(_text("menu.invalid") % choice)

    def _msa_source(self):
        """Collect the alignment source: pasted inline text or an external
        path — exactly one, as the service requires."""
        route = self._ask("menu.ask_msa_route").lower()
        if route in ("i", "inline"):
            content = self._console.read_multiline(
                _text("menu.msa_inline_header") + "\n"
            ).decode("utf-8", "replace")
            return content or None, None
        if route in ("e", "external", "path"):
            return None, self._pick_path("menu.ask_msa_path") or None
        return None, None

    def _set_protein_alignment(self, configuration) -> None:
        record_key = self._ask("menu.msa_record_prompt")
        self._alignment_for(configuration, record_key, "protein")

    def _set_rna_alignment(self, configuration) -> None:
        record_key = self._ask("menu.msa_record_prompt")
        self._alignment_for(configuration, record_key, "rna")

    def _alignment_for(self, configuration, record_key: str, family: str) -> None:
        """Collect mode (+ source when the mode carries one) and dispatch."""
        mode = self._msa_mode(family)
        if mode in ("automatic", "free"):
            self._report(configuration.set_alignment(record_key, mode))
            return
        inline_text, external_path = self._msa_source()
        self._report(
            configuration.set_alignment(
                record_key, mode, inline_text=inline_text, external_path=external_path
            )
        )

    def _set_references(self, configuration) -> None:
        record_key = self._ask("menu.msa_record_prompt")
        self._references_for(record_key)

    def _references_for(self, record_key: str) -> None:
        """Collect the template route and dispatch (shared with the add flow)."""
        configuration = self._services.configuration
        route = self._ask("menu.ask_templates_route").strip().lower()
        if route in ("n", ""):
            self._report(configuration.set_references(record_key))
            return
        if route in ("e", "none"):
            self._report(configuration.set_references(record_key, references=()))
            return
        if route not in ("p", "provide", "list"):
            self._say(_text("menu.invalid") % route)
            return
        external_path = self._pick_path("menu.ask_ref_path") or None
        raw_pairs = self._ask("menu.ask_ref_pairs").strip()
        pairs = []
        if raw_pairs:
            for token in raw_pairs.split(","):
                left, _, right = token.strip().partition(":")
                pairs.append((left.strip(), right.strip()))
        self._report(
            configuration.set_references(
                record_key,
                references=(
                    ReferenceInput(external_path=external_path, pairs=pairs),
                ),
            )
        )

    # -- structural sections ------------------------------------------------

    def _bonded_pairs(self) -> None:
        configuration = self._services.configuration
        while True:
            project = self._project()
            if project is None:
                return
            self._say(_banner(_text("menu.pairs_title"), self._width))
            self._say()
            self._say(_text("menu.linkage_count") % len(project.configuration.linkages))
            self._say()
            self._say(_text("menu.pairs_actions"))
            self._say()
            self._say(_text("menu.back"))
            choice = self._select()
            if choice in ("0", "q", "back"):
                return
            elif choice == "1":
                self._add_linkage(configuration)
            elif choice == "2":
                if self._report(configuration.remove_linkage(self._ask("menu.ask_position"))):
                    self._say(_text("menu.linkage_removed"))
            elif choice:
                self._say(_text("menu.invalid") % choice)

    def _add_linkage(self, configuration) -> None:
        a_key = self._ask("menu.ask_record")
        a_residue = self._ask("menu.ask_residue_a")
        a_atom = self._ask("menu.ask_atom_a")
        b_key = self._ask("menu.ask_record")
        b_residue = self._ask("menu.ask_residue_b")
        b_atom = self._ask("menu.ask_atom_b")
        if self._report(
            configuration.add_linkage(a_key, a_residue, a_atom, b_key, b_residue, b_atom)
        ):
            self._say(_text("menu.linkage_added"))

    def _custom_ccd(self) -> None:
        configuration = self._services.configuration
        while True:
            if self._project() is None:
                return
            self._say(_banner(_text("menu.ccd_title"), self._width))
            self._say()
            self._say(_text("menu.ccd_actions"))
            self._say()
            self._say(_text("menu.back"))
            choice = self._select()
            if choice in ("0", "q", "back"):
                return
            elif choice == "1":
                self._paste_component_definition(configuration)
            elif choice == "2":
                self._add_modification(configuration)
            elif choice == "3":
                self._remove_modification(configuration)
            elif choice:
                self._say(_text("menu.invalid") % choice)

    def _paste_component_definition(self, configuration) -> None:
        content = self._console.read_multiline(
            _text("menu.paste_definition") + "\n"
        ).decode("utf-8", "replace")
        if self._report(configuration.set_component_definition(inline_text=content)):
            self._say(_text("menu.component_set"))

    def _add_modification(self, configuration) -> None:
        record_key = self._ask("menu.ask_record")
        code = self._ask("menu.ask_code")
        position = self._ask("menu.ask_position")
        if self._report(configuration.add_modification(record_key, code, position)):
            self._say(_text("menu.modification_added"))

    def _remove_modification(self, configuration) -> None:
        record_key = self._ask("menu.ask_record")
        index = self._ask("menu.ask_position")
        if self._report(configuration.remove_modification(record_key, index)):
            self._say(_text("menu.modification_removed"))

    # -- summary --------------------------------------------------------------

    def _summary_screen(self) -> None:
        project = self._project()
        if project is None:
            return
        summary = _summary_of(project.configuration)
        self._say(_banner(_text("menu.wizard_summary"), self._width))
        self._say()
        self._say(_text("menu.summary_line") % ("name", summary["job_name"]))
        self._say(_text("menu.summary_line") % ("version", summary["format_version"]))
        self._say(_text("menu.summary_line") % ("seeds", summary["seed_values"]))
        for family, label in (
            ("protein", "proteins"),
            ("rna", "rna"),
            ("dna", "dna"),
            ("ligand", "ligands"),
        ):
            rows = summary["entity_groups"][family]
            self._say(
                _text("menu.summary_line")
                % (label, len(rows) if rows else _text("menu.none"))
            )
        self._say()
        for record in project.configuration.records:
            self._say(_entity_line(record))
        self._say()
        self._say(_text("menu.specs_header"))
        specs = project.specs
        if not specs:
            self._say(_text("menu.specs_none"))
        else:
            for spec in specs:
                self._say(_text("menu.spec_line") % (spec.key, spec.label))

    # -- validation ------------------------------------------------------------

    def _validation(self) -> None:
        from configbuilder.ui.present import format_findings

        while True:
            if self._project() is None:
                return
            self._say(_banner(_text("menu.validation_title"), self._width))
            self._say()
            self._say(_text("menu.validation_actions"))
            self._say()
            self._say(_text("menu.back"))
            choice = self._select()
            if choice in ("0", "q", "back"):
                return
            elif choice == "1":
                self._validate_base(format_findings)
            elif choice == "2":
                self._validate_all(format_findings)
            elif choice:
                self._say(_text("menu.invalid") % choice)

    def _print_cards(self, findings, format_findings) -> None:
        """Findings as the numbered cards the present layer produces —
        the same display discipline as the wizard's report screen."""
        for card in format_findings(findings, width=self._width):
            self._say(
                _text("menu.card_line")
                % (card.number, card.severity_line, card.context)
            )
            for line in card.lines:
                self._say(_text("menu.finding_indent") + line)

    def _validate_base(self, format_findings) -> None:
        outcome = self._services.validation.validate_base()
        if not outcome.ok and outcome.report is None:
            self._say(_text("menu.not_applied") % (outcome.message or ""))
            return
        findings = outcome.report.findings
        self._say(_text("menu.ok") % "base" if not findings else _text("menu.fail") % "base")
        self._print_cards(findings, format_findings)

    def _validate_all(self, format_findings) -> None:
        outcome = self._services.validation.validate_all()
        base_report = outcome.base_report
        if base_report is None:
            self._say(_text("menu.no_project"))
            return
        base_blocking = bool(base_report.blocking())
        self._say(_text("menu.ok") % "base" if not base_blocking else _text("menu.fail") % "base")
        if base_blocking:
            self._print_cards(base_report.findings, format_findings)
        for key in outcome.variant_reports:
            report = outcome.variant_reports[key]
            blocking = bool(report.blocking())
            self._say(_text("menu.ok") % key if not blocking else _text("menu.fail") % key)
            if blocking:
                self._print_cards(report.findings, format_findings)

    # -- JSON display ------------------------------------------------------------

    def _show_json(self, key=None) -> None:
        text_json, error = self._services.generation.show_json(key)
        if error is not None:
            self._say(_text("menu.json_error") % error)
            return
        self._say(text_json)

    # -- variants ------------------------------------------------------------------

    # -- variants: shared numbered-choice machinery ------------------------

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
        choice = self._select()
        if choice in ("0", "q", "back", ""):
            return None
        if choice.isdigit() and 1 <= int(choice) <= len(entries):
            return entries[int(choice) - 1][1]
        self._say(_text("menu.invalid") % choice)
        return self._numbered_choice(None, entries, back_note)  # re-ask

    def _choice_menu(self, title, choices):
        """Numbered menu over ``VariantChoice`` rows → the payload value.
        The rows carry data (keys), not wording; entity rows are rendered
        through this module's registered entity-line templates."""
        if not choices:
            self._say(_text("menu.entity_add_note"))
            return None
        entries = [(self._choice_label(choice), choice.value) for choice in choices]
        return self._numbered_choice(title, entries)

    def _choice_label(self, choice) -> str:
        """Human wording for one choice row: entity keys are rendered
        through the entity-line templates; other rows carry their own
        registered labels (set at the call site)."""
        if choice.kind in ("protein", "rna", "dna", "ligand", "entity"):
            project = self._project()
            if project is not None:
                for record in project.configuration.records:
                    if record.ids.primary.value == choice.value:
                        return _entity_line(record).strip()
        return choice.label

    def _variants_menu(self) -> None:
        """The job-first variants section: the current job picture first,
        base JSON as the primary action, variants as the optional,
        explicitly-entered workflow beneath it."""
        while True:
            project = self._project()
            if project is None:
                return
            self._say(_banner(_text("menu.variants_title"), self._width))
            self._say()
            self._say_job_picture(project)
            self._say_variant_list(project)
            self._say()
            self._say(_text("menu.variant_actions"))
            self._say()
            self._say(_text("menu.back"))
            choice = self._select()
            if choice in ("0", "q", "back"):
                return
            elif choice == "1":
                self._generate_base_json()
            elif choice == "2":
                self._create_variant()
            elif choice == "3":
                self._manage_variants()
            elif choice == "4":
                self._batch_from_file()
            elif choice == "5":
                self._quantity_series()
            elif choice:
                self._say(_text("menu.invalid") % choice)

    def _quantity_series(self) -> None:
        """The concentration/quantity series — a **variant** operation,
        reachable only here (never in the add-component flow). Component
        selection, progression, preview, confirmation, then one
        independent variant per level through the service."""
        choices = self._services.variants.component_count_choices()
        if not choices:
            self._say(_text("menu.series_no_components"))
            return
        # -- component selection (numbered; no internal ids typed) ----
        rows = [(choice.value, choice.detail) for choice in choices]
        entries = [("%s  %s" % (key, _text("menu.series_preview_times") % count), key)
                   for key, count in rows]
        self._say(_banner(_text("menu.series_component_menu"), self._width))
        self._say()
        for index, (label, _) in enumerate(entries, start=1):
            self._say(_text("menu.choice_line") % (index, label))
        self._say(_text("menu.choice_line") % (
            len(entries) + 1, _text("menu.series_component_multiple")))
        self._say()
        self._say(_text("menu.back"))
        raw = self._select()
        if raw in ("0", "q", "back", ""):
            return
        selected = []
        if raw.strip() == str(len(entries) + 1):
            selected = [key for _, key in entries]
        elif all(part.isdigit() and 1 <= int(part) <= len(entries)
                 for part in raw.split()):
            seen = []
            for part in raw.split():
                key = entries[int(part) - 1][1]
                if key not in seen:
                    seen.append(key)
            selected = seen
        else:
            self._say(_text("menu.invalid") % raw)
            return
        if not selected:
            return
        # -- progression -----------------------------------------------
        numbers = {}
        for prompt_key, name in (
            ("menu.series_start_prompt", "start"),
            ("menu.series_factor_prompt", "factor"),
            ("menu.series_levels_prompt", "levels"),
        ):
            answer = self._ask(prompt_key)
            if answer in ("0", "q", "back", "") or not answer.strip().isdigit():
                self._say(_text("menu.series_bad_value"))
                return
            numbers[name] = int(answer)
        rows_plan, failure = self._services.variants.quantity_series_plan(
            selected, numbers["start"], numbers["factor"], numbers["levels"]
        )
        if failure is not None:
            self._say(_text("menu.not_applied") % failure)
            return
        # -- preview, then confirm (nothing exists until Yes) ----------
        self._say()
        self._say(_banner(_text("menu.series_preview_title"), self._width))
        self._say()
        self._say(_text("menu.series_preview_base"))
        for key, count in rows:
            if key in selected:
                self._say(_text("menu.series_preview_row") % (
                    key, _text("menu.series_preview_times") % count))
        self._say(_text("menu.series_preview_factor") % (
            numbers["factor"], numbers["levels"]))
        self._say()
        self._say(_text("menu.series_preview_will"))
        for multiplier, counts in rows_plan:
            parts = "  ".join(
                "%s %s" % (key, _text("menu.series_preview_times") % count)
                for key, count in sorted(counts.items())
            )
            self._say(_text("menu.series_preview_row") % (
                "x%d" % multiplier, parts))
        self._say()
        confirm = self._numbered_choice(_text("menu.series_confirm"), [
            (_text("menu.series_yes"), True),
            (_text("menu.series_no"), False),
        ], back_note=False)
        if not confirm:
            return
        outcome = self._services.variants.create_quantity_series(
            selected, numbers["start"], numbers["factor"], numbers["levels"]
        )
        if outcome.ok:
            self._say(_text("menu.series_created") % len(rows_plan))
        else:
            self._say(_text("menu.not_applied") % outcome.message)

    def _manage_variants(self) -> None:
        """Variant management, entered explicitly — CRUD and preview over
        the variants that exist, never a gate in front of the base."""
        while True:
            project = self._project()
            if project is None:
                return
            self._say(_banner(_text("menu.variants_title"), self._width))
            self._say()
            self._say_variant_list(project)
            self._say()
            self._say(_text("menu.manage_actions"))
            self._say()
            self._say(_text("menu.back"))
            choice = self._select()
            if choice in ("0", "q", "back"):
                return
            elif choice == "1":
                self._edit_variant()
            elif choice == "2":
                self._duplicate_variant()
            elif choice == "3":
                self._delete_variant()
            elif choice == "4":
                self._preview_variant()
            elif choice == "5":
                self._json_preview_variant()
            elif choice:
                self._say(_text("menu.invalid") % choice)

    def _generate_base_json(self) -> None:
        """Base JSON as a first-class action: validate → transform →
        encode → plan → confirm → write, all through the generation
        service (the same pipeline a variant run uses, with the base as
        the run's only entry). The UI never serializes anything."""
        from configbuilder.ui.present import format_findings

        project = self._project()
        if project is None:
            return
        generation_plan = self._services.generation.plan_base(self._output_dir)
        if not generation_plan.ok:
            self._plan_failure(generation_plan, format_findings)
            return
        self._say()
        self._say(_text("menu.preview_name") % generation_plan.project_name)
        self._say(_text("menu.preview_entities"))
        for record in project.configuration.records:
            self._say("  " + _entity_line(record))
        self._say(_text("menu.preview_seeds") % (list(project.configuration.seeds.values),))
        self._say(_text("menu.export_dir") % generation_plan.output_root)
        for entry in generation_plan.entries:
            self._say(_text("menu.export_action_line") % (entry.action, entry.path))
        for warning in generation_plan.warnings:
            self._say(_text("menu.export_warning") % warning)
        entries = [
            (_text("menu.base_generate"), True),
            (_text("menu.base_back"), False),
        ]
        proceed = self._numbered_choice(_text("menu.base_confirm"), entries, back_note=False)
        if not proceed:
            return
        result = self._services.generation.execute(generation_plan)
        if result.ok:
            for path in result.written:
                self._say(_text("menu.export_written") % path)
            for path in result.skipped:
                self._say(_text("menu.export_skipped") % path)
        else:
            for error in result.errors:
                self._say(_text("menu.not_applied") % error)

    def _say_job_picture(self, project) -> None:
        """The base job as the variants screen shows it: entities grouped
        by family (the model's own order), seeds, version."""
        configuration = project.configuration
        self._say(_banner(_text("menu.job_header"), self._width))
        self._say()
        self._say(_text("menu.preview_name") % configuration.metadata.name)
        selection = configuration.format_target.version_selection
        version = fold_version_selection(
            selection,
            lambda: _text("menu.version_unverified"),
            lambda version: _text("menu.version_pinned") % version,
            lambda evidenced: _text("menu.version_auto"),
        )
        self._say(_text("menu.job_version_line") % version)
        self._say()
        shown = False
        for family, type_ in _FAMILY_TYPES:
            records = [r for r in configuration.records if isinstance(r, type_)]
            if not records:
                continue
            shown = True
            self._say(_text("menu.job_family_header") % family)
            for record in records:
                self._say(_entity_line(record))
        if not shown:
            self._say(_text("menu.entity_list_empty"))
        self._say()
        self._say(_text("menu.preview_seeds") % (list(configuration.seeds.values),))

    def _change_line(self, kind: str, described: dict) -> str:
        """One variant change row, rendered through registered templates
        from the app layer's described-edit data."""
        record = described.get("record_key", "") or "?"
        if kind == "SetName":
            return _text("menu.change_name") % described.get("job_name", "")
        if kind == "SetJobDescription":
            return _text("menu.change_description")
        if kind == "SetDescription":
            return _text("menu.change_record_description") % record
        if kind == "SetSeeds":
            return _text("menu.change_seeds") % described.get("seeds", [])
        if kind == "SetSequence":
            return _text("menu.change_sequence") % record
        if kind == "AddModification":
            return _text("menu.change_add_mod") % (
                record,
                described.get("code", "?"),
                described.get("position", "?"),
            )
        if kind == "RemoveModification":
            return _text("menu.change_remove_mod") % (int(described.get("index", -1)) + 1)
        if kind in ("SetAlignment", "SetSingleAlignment"):
            return _text("menu.change_alignment") % record
        if kind == "SetReferences":
            return _text("menu.change_references") % record
        if kind == "SetComponentDefinition":
            return _text("menu.change_component_definition")
        if kind == "SetFormatTarget":
            return _text("menu.change_format_target")
        if kind == "SetComponentRepresentation":
            return _text("menu.change_component_representation")
        if kind == "SetComponentCount":
            return _text("menu.change_component_count") % (
                record,
                described.get("count", "?"),
            )
        if kind == "AddRecord":
            return _text("menu.spec_add_record")
        if kind == "RemoveRecord":
            return _text("menu.change_remove_record") % record
        if kind in ("AddLinkage", "RemoveLinkage"):
            return _text("menu.change_linkage")
        return _text("menu.change_generic") % kind

    def _say_variant_list(self, project) -> None:
        """The variant list with per-variant change summaries (rendered
        here from the app layer's described edits — never re-derived)."""
        self._say(_banner(_text("menu.specs_header"), self._width))
        self._say()
        if not project.specs:
            self._say(_text("menu.specs_none"))
            return
        for index, spec in enumerate(project.specs, start=1):
            self._say(_text("menu.spec_entry") % (index, spec.key, spec.label))
            for kind, described, _record in self._services.variants.spec_change_descriptions(spec.key):
                self._say(_text("menu.spec_edits_line") % self._change_line(kind, described))

    def _select_variant(self, title=None):
        """Numbered variant selection → the spec key (or ``None``)."""
        project = self._project()
        if project is None:
            return None
        if not project.specs:
            self._say(_text("menu.specs_none"))
            return None
        entries = [
            ("%s — %s" % (spec.key, spec.label), spec.key) for spec in project.specs
        ]
        return self._numbered_choice(title, entries)

    def _select_entity(self, family=None, title=None):
        """Numbered entity selection → the record key (or ``None``)."""
        choices = (
            self._services.variants.entity_choices(family)
            if family
            else self._services.variants.all_entity_choices()
        )
        return self._choice_menu(title or _text("menu.select_entity"), choices)

    def _ask_name(self):
        """Naming submenu: custom name or automatic. Returns ``(key,
        label)`` or ``None`` to cancel."""
        entries = [
            (_text("menu.name_custom"), "custom"),
            (_text("menu.name_auto"), "auto"),
        ]
        route = self._numbered_choice(_text("menu.name_menu"), entries)
        if route is None:
            return None
        if route == "custom":
            name = self._ask("menu.custom_name_prompt")
            if not name:
                return None
            return name, name
        return self._auto_name(), self._auto_name()

    def _auto_name(self):
        """The next free ``variant_N`` name — deterministic, ordered."""
        project = self._project()
        used = {spec.key for spec in project.specs}
        index = 1
        while "variant_%d" % index in used:
            index += 1
        return "variant_%d" % index

    def _create_variant(self) -> None:
        naming = self._ask_name()
        if naming is None:
            return
        key, label = naming
        outcome = self._services.variants.add_spec(key, label or key, ())
        if not outcome.ok:
            self._say(_text("menu.not_applied") % (outcome.message or "refused"))
            return
        self._say(_text("menu.created") % key)
        self._variant_change_flow(key, creating=True)

    def _edit_variant(self) -> None:
        key = self._select_variant()
        if key is None:
            return
        self._variant_change_flow(key, creating=False)

    def _variant_change_flow(self, key: str, creating: bool) -> None:
        """The change picker shared by create and edit: numbered change
        kinds, then the per-kind submenus, looping until Back. Every
        edit is built in ``app`` (``apply_variant_edit``) — the UI only
        collects selections and free-form values."""
        while True:
            options = self._services.variants.edit_options()
            entries = [(option.label, option.kind) for option in options]
            kind = self._numbered_choice(_text("menu.select_change"), entries)
            if kind is None:
                return
            if not self._collect_change(key, kind):
                continue
            if creating:
                return

    def _collect_change(self, key: str, kind: str) -> bool:
        """One change, fully collected and applied. True when it landed."""
        service = self._services.variants
        if kind == "sequence":
            record_key = self._select_entity(title=_text("menu.select_entity"))
            if record_key is None:
                return False
            sequence = self._ask("menu.ask_sequence")
            if not sequence:
                return False
            self._report(service.apply_variant_edit(key, kind, sequence, record_key=record_key))
            return True
        if kind in ("job_name", "job_description", "seeds"):
            prompt_key = {
                "job_name": "menu.new_name_prompt",
                "job_description": "menu.new_desc_prompt",
                "seeds": "menu.seeds_prompt",
            }[kind]
            value = self._ask(prompt_key)
            if not value:
                return False
            self._report(service.apply_variant_edit(key, kind, value))
            return True
        if kind == "add_modification":
            record_key = self._select_entity(title=_text("menu.select_entity"))
            if record_key is None:
                return False
            code = self._ask("menu.mod_code_prompt")
            if not code:
                return False
            raw = self._ask("menu.ask_position")
            if not raw.isdigit() or int(raw) < 1:
                self._say(_text("menu.invalid") % raw)
                return False
            self._report(service.apply_variant_edit(key, kind, (code, int(raw)), record_key=record_key))
            return True
        if kind == "remove_modification":
            record_key = self._select_entity(title=_text("menu.select_entity"))
            if record_key is None:
                return False
            return self._remove_modification_flow(
                key, record_key, service.modification_summary(key)
            )
        if kind == "alignment":
            return self._collect_alignment(key)
        if kind == "references":
            return self._collect_references(key)
        if kind == "add_entity":
            return self._collect_add_entity(key)
        if kind == "remove_entity":
            record_key = self._select_entity(title=_text("menu.select_entity"))
            if record_key is None:
                return False
            self._report(service.apply_variant_edit(key, kind, None, record_key=record_key))
            return True
        self._say(_text("menu.invalid") % kind)
        return False

    def _remove_modification_flow(self, key, record_key, summary) -> bool:
        """Numbered removal over the variant's own modification edits."""
        mine = [
            (index, label)
            for index, label in summary
            if label.startswith(record_key + " ")
        ]
        if not mine:
            self._say(_text("menu.no_modifications"))
            return False
        entries = [(label, index) for index, label in mine]
        index = self._numbered_choice(_text("menu.mod_remove_prompt"), entries)
        if index is None:
            return False
        self._report(
            self._services.variants.apply_variant_edit(
                key, "remove_modification", index, record_key=record_key
            )
        )
        return True

    def _collect_alignment(self, key: str) -> bool:
        record_key = self._select_entity(title=_text("menu.select_entity"))
        if record_key is None:
            return False
        entries = [
            (_text("menu.msa_mode_auto"), "automatic"),
            (_text("menu.msa_mode_unpaired"), "unpaired"),
            (_text("menu.msa_mode_paired"), "paired"),
            (_text("menu.msa_mode_both"), "both"),
            (_text("menu.msa_mode_free"), "free"),
        ]
        mode = self._numbered_choice(_text("menu.msa_mode_menu"), entries)
        if mode is None:
            return False
        source = None
        if mode not in ("automatic", "free"):
            source = self._msa_source_payload()
            if source is None:
                return False
        self._report(
            self._services.variants.apply_variant_edit(
                key, "alignment", (mode, source), record_key=record_key
            )
        )
        return True

    def _msa_source_payload(self):
        """Inline paste or file, as an app-layer ``('inline'|'file',
        text)`` payload — ``None`` on cancel."""
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

    def _collect_references(self, key: str) -> bool:
        record_key = self._select_entity(title=_text("menu.select_entity"))
        if record_key is None:
            return False
        entries = [
            (_text("menu.templates_search"), "search"),
            (_text("menu.templates_none"), "none"),
            (_text("menu.templates_list"), "list"),
        ]
        route = self._numbered_choice(_text("menu.templates_menu"), entries)
        if route is None:
            return False
        payload = None
        if route == "list":
            path = self._pick_path("menu.template_path_prompt")
            if not path:
                return False
            raw_pairs = self._ask("menu.template_pairs_prompt").strip()
            pairs = []
            for token in raw_pairs.split(","):
                if not token.strip():
                    continue
                left, _, right = token.strip().partition(":")
                pairs.append((left.strip(), right.strip()))
            payload = [("file", path, pairs)]
        self._report(
            self._services.variants.apply_variant_edit(
                key, "references", (route, payload), record_key=record_key
            )
        )
        return True

    def _collect_add_entity(self, key: str) -> bool:
        """Guided add-entity: family → (sequence | representation) → the
        service builds the record(s) — the DNA duplex rides through."""
        entries = [
            (_text("menu.family_protein"), "protein"),
            (_text("menu.family_rna"), "rna"),
            (_text("menu.family_dna"), "dna"),
            (_text("menu.family_ligand"), "ligand"),
        ]
        family = self._numbered_choice(_text("menu.add_entity_family"), entries)
        if family is None:
            return False
        if family == "ligand":
            kind = self._ligand_kind()
            if kind is None:
                return False
            representation = self._ask("menu.ligand_repr_prompt")
            if not representation:
                return False
            records, error = self._services.variants.build_add_records(
                family, "", representation=representation, representation_kind=kind
            )
        else:
            sequence = self._ask(_text("menu.entity_seq_prompt") % family)
            if not sequence:
                return False
            records, error = self._services.variants.build_add_records(
                family, sequence
            )
        if error is not None:
            self._say(_text("menu.not_applied") % error)
            return False
        self._report(
            self._services.variants.apply_variant_edit(key, "add_entity", records)
        )
        return True

    def _duplicate_variant(self) -> None:
        source = self._select_variant()
        if source is None:
            return
        naming = self._ask_name()
        if naming is None:
            return
        new_key, label = naming
        outcome = self._services.variants.duplicate_spec(source, new_key, label or "")
        if outcome.ok:
            self._say(_text("menu.copied") % new_key)
        else:
            self._say(_text("menu.not_applied") % (outcome.message or "refused"))

    def _delete_variant(self) -> None:
        key = self._select_variant()
        if key is None:
            return
        entries = [(_text("menu.delete_yes"), True), (_text("menu.delete_no"), False)]
        confirmed = self._numbered_choice(
            _text("menu.delete_confirm") % key, entries, back_note=False
        )
        if not confirmed:
            return
        outcome = self._services.variants.remove_spec(key)
        if outcome.ok:
            self._say(_text("menu.removed") % key)
        else:
            self._say(_text("menu.not_applied") % (outcome.message or "refused"))

    def _preview_variant(self) -> None:
        key = self._select_variant()
        if key is None:
            return
        project = self._project()
        if project is None:
            return
        outcome = self._services.variants.preview(key)
        if not outcome.ok:
            self._say(_text("menu.not_applied") % (outcome.message or "failed"))
            return
        variant = outcome.variants[0]
        summary = _summary_of(variant.configuration)
        self._say(_banner(_text("menu.preview_header") + ": " + key, self._width))
        self._say()
        self._say(_text("menu.preview_base_line") % summary["job_name"])
        self._say()
        self._say(_text("menu.preview_changes"))
        for kind, described, _record in self._services.variants.spec_change_descriptions(key):
            self._say(_text("menu.preview_change_line") % self._change_line(kind, described))
        self._say()
        self._say(_text("menu.preview_name") % summary["job_name"])
        self._say(_text("menu.preview_seeds") % (summary["seed_values"],))
        self._say(_text("menu.preview_entities"))
        for record in variant.configuration.records:
            self._say(_entity_line(record))
        self._say()
        self._say(
            _text("menu.preview_output")
            % self._file_name_for(project.configuration.metadata.name, key)
        )
        answer = self._ask("menu.ask_show_json")
        if answer.lower() in ("y", "yes"):
            self._show_json(key)

    def _json_preview_variant(self) -> None:
        """JSON preview through numbered selection; the serialization is
        the generation service's (``show_json``), never the UI's."""
        key = self._select_variant()
        if key is None:
            return
        self._show_json(key)

    def _batch_from_file(self) -> None:
        """Batch generation with a confirm step: pick the file, show what
        was detected (the parsed entries, before anything is created),
        then create — through the same all-or-nothing service call."""
        path = self._pick_path("menu.ask_sequence_file")
        if not path:
            return
        detected = self._services.variants.inspect_sequence_file(path)
        if not detected.ok:
            self._say(_text("menu.not_applied") % (detected.message or "refused"))
            return
        self._say()
        self._say(_text("menu.batch_file_line") % path)
        self._say(_text("menu.batch_detected"))
        for index, entry in enumerate(detected.entries, start=1):
            self._say(_text("menu.batch_entry_line") % (index, entry))
        self._say()
        entries = [
            (_text("menu.batch_create_all"), True),
            (_text("menu.batch_cancel"), False),
        ]
        proceed = self._numbered_choice(_text("menu.batch_what_now"), entries, back_note=False)
        if not proceed:
            return
        outcome = self._services.variants.generate_from_file(path)
        if outcome.ok:
            self._say(_text("menu.batch_done") % outcome.message)
        else:
            self._say(_text("menu.not_applied") % (outcome.message or "refused"))

    def _file_name_for(self, project_name: str, key: str) -> str:
        """The same naming function the export uses — imported through
        ``app``'s generation module (``ui`` never re-derives names)."""
        from configbuilder.app.generation_service import variant_file_name

        return variant_file_name(project_name, key)

    # -- export ------------------------------------------------------------------

    def _export_menu(self) -> None:
        from configbuilder.ui.present import format_findings

        project = self._services.projects.project
        if project is not None and not project.specs:
            # No variants: base JSON generation is the whole story here.
            self._export_menu_with_base()
            return
        while True:
            project = self._project()
            if project is None:
                return
            specs = project.specs
            self._say(_banner(_text("menu.export_header"), self._width))
            self._say()
            self._say(_text("menu.export_ready") % len(specs))
            if not specs:
                self._say(_text("menu.export_empty_hint"))
            for spec in specs:
                self._say("  " + _text("menu.spec_line") % (spec.key, spec.label))
            self._say()
            self._say(_text("menu.export_dir") % self._output_dir)
            self._say()
            self._say(_text("menu.export_actions"))
            self._say()
            self._say(_text("menu.back"))
            choice = self._select()
            if choice in ("0", "q", "back"):
                return
            elif choice == "1":
                self._export(None, format_findings)
            elif choice == "2":
                raw = self._ask("menu.export_which")
                keys = [k.strip() for k in raw.split(",") if k.strip()]
                self._export(keys or None, format_findings)
            elif choice == "3":
                new_dir = self._pick_path("menu.ask_export_dir")
                if new_dir:
                    self._output_dir = new_dir
                    self._say(_text("menu.export_dir_changed") % new_dir)
            elif choice == "4":
                self._preview_export()
            elif choice:
                self._say(_text("menu.invalid") % choice)

    def _export_menu_with_base(self) -> None:
        """The JSON-generation screen when no variants exist: base
        generation *is* the primary action, so the menu offers it
        directly instead of refusing (§13: JSON generation never hides
        behind variant management)."""
        while True:
            project = self._project()
            if project is None:
                return
            self._say(_banner(_text("menu.export_base_header"), self._width))
            self._say()
            self._say(_text("menu.export_base_hint"))
            self._say()
            self._say(_text("menu.export_base_actions"))
            self._say()
            self._say(_text("menu.back"))
            choice = self._select()
            if choice in ("0", "q", "back"):
                return
            elif choice == "1":
                self._generate_base_json()
            elif choice == "2":
                new_dir = self._pick_path("menu.ask_export_dir")
                if new_dir:
                    self._output_dir = new_dir
                    self._say(_text("menu.export_dir_changed") % new_dir)
            elif choice:
                self._say(_text("menu.invalid") % choice)
                new_dir = self._pick_path("menu.ask_export_dir")
                if new_dir:
                    self._output_dir = new_dir
                    self._say(_text("menu.export_dir_changed") % new_dir)
            elif choice == "4":
                self._preview_export()
            elif choice:
                self._say(_text("menu.invalid") % choice)

    def _plan_failure(self, generation_plan, format_findings) -> None:
        """A refused plan: the message, and — when the refusal came from
        validation — the actual blocking findings, so the user sees which
        rule and which record stand in the way instead of a bare verdict."""
        self._say(_text("menu.not_applied") % (generation_plan.message or ""))
        if generation_plan.findings:
            self._print_cards(generation_plan.findings, format_findings)

    def _preview_export(self) -> None:
        from configbuilder.ui.present import format_findings

        generation_plan = self._services.generation.plan(self._output_dir)
        if not generation_plan.ok:
            self._plan_failure(generation_plan, format_findings)
            return
        for warning in generation_plan.warnings:
            self._say(_text("menu.export_warning") % warning)
        for entry in generation_plan.entries:
            self._say(_text("menu.export_would_write") % (entry.path, entry.action))
        self._say()
        self._say(_text("menu.export_preview_note"))

    def _export(self, keys, format_findings) -> None:
        """Validate (base + selected variants), plan, execute. Validation
        failures name the variant and the finding; nothing is written on
        a blocking report (plan §15's fixed sequence, unchanged)."""
        generation_plan = self._services.generation.plan(self._output_dir, only=keys)
        if not generation_plan.ok:
            self._plan_failure(generation_plan, format_findings)
            return
        for warning in generation_plan.warnings:
            self._say(_text("menu.export_warning") % warning)
        for conflict in generation_plan.conflicts:
            self._say(_text("menu.export_conflict") % conflict)
            return
        for entry in generation_plan.entries:
            self._say(_text("menu.export_action_line") % (entry.action, entry.path))
        answer = self._ask("menu.ask_proceed")
        if answer.lower() not in ("y", "yes"):
            return
        result = self._services.generation.execute(generation_plan)
        if result.ok:
            for path in result.written:
                self._say(_text("menu.export_written") % path)
            for path in result.skipped:
                self._say(_text("menu.export_skipped") % path)
            self._say(_text("menu.export_dir") % self._output_dir)
        else:
            for error in result.errors:
                self._say(_text("menu.not_applied") % error)
