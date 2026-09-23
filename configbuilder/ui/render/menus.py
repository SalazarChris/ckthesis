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

    def _pick_path(self, prompt_key: str) -> str:
        """Choose a path with the keyboard alone: the current directory is
        listed, numbers open directories or select files, ``..`` goes up,
        and anything else typed is taken as a literal path — so pasting a
        full path still works. Cancellation is ``0`` or an empty answer;
        the service layer remains the authority on whether the path exists
        or is usable."""
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
            if raw in ("", "0", "q", "quit", "exit"):
                return ""
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
        # anything else (blank, unknown, EOF) declines and lets the caller exit

    def _save_project(self) -> None:
        projects = self._services.projects
        if projects.project is None:        self._say(_text("menu.no_project"))
        return
        path = self._pick_path("menu.ask_path")
        result = projects.save_as(path) if path else projects.save()
        if result.ok:
            self._say(_text("menu.saved_to") % (projects.path or path))
        else:
            self._say(_text("menu.not_applied") % (result.message or "refused"))

    def _load_project(self) -> None:
        path = self._pick_path("menu.ask_path")
        if not path:
            return
        result = self._services.projects.open(path)
        if result.ok:
            self._say(_text("menu.loaded") % path)
        else:
            self._say(_text("menu.load_failed") % (result.message or "failed"))

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

    def _add_entity(self, family: str) -> None:
        prompts = {
            "protein": "menu.add_protein_prompt",
            "rna": "menu.add_rna_prompt",
            "dna": "menu.add_dna_prompt",
            "ligand": "menu.add_ligand_prompt",
        }
        if family == "ligand":
            representation = self._ask(prompts[family])
            self._report(
                self._services.configuration.add_record(
                    "ligand", representation=representation
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
        record_key = self._ask("menu.ask_record")
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

    def _variants_menu(self) -> None:
        variants = self._services.variants
        while True:
            project = self._project()
            if project is None:
                return
            specs = project.specs
            self._say(_banner(_text("menu.variants_title"), self._width))
            self._say()
            self._say(_text("menu.base_label") + ":")
            for record in project.configuration.records:
                self._say(_entity_line(record))
            self._say()
            self._say(_text("menu.specs_header"))
            if not specs:
                self._say(_text("menu.specs_none"))
            else:
                for index, spec in enumerate(specs, start=1):
                    self._say(
                        _text("menu.numbered_spec") % (index, spec.key, spec.label)
                    )
            self._say()
            self._say(_text("menu.variant_actions"))
            self._say()
            self._say(_text("menu.back"))
            choice = self._select()
            if choice in ("0", "q", "back"):
                return
            elif choice == "1":
                self._create_variant()
            elif choice == "2":
                self._edit_variant()
            elif choice == "3":
                self._duplicate_variant()
            elif choice == "4":
                self._delete_variant()
            elif choice == "5":
                self._preview_variant()
            elif choice == "6":
                self._show_json(self._ask("menu.ask_source") or None)
            elif choice == "7":
                self._batch_from_file()
            elif choice:
                self._say(_text("menu.invalid") % choice)

    def _batch_from_file(self) -> None:
        """Generate one independent variant per sequence in a ``.txt``
        file. The UI reads nothing and builds nothing: it passes the path
        to the service and reports the outcome — the batch logic lives in
        ``app`` (spec construction) and ``persistence`` (file reading)."""
        path = self._pick_path("menu.ask_sequence_file")
        if not path:
            return
        outcome = self._services.variants.generate_from_file(path)
        if outcome.ok:
            self._say(_text("menu.batch_done") % outcome.message)
        else:
            self._say(_text("menu.not_applied") % (outcome.message or "refused"))

    def _create_variant(self) -> None:
        key = self._ask("menu.ask_key")
        label = self._ask("menu.ask_label")
        outcome = self._services.variants.add_spec(key, label or key, ())
        if outcome.ok:
            self._say(_text("menu.created") % key)
            self._say(_text("menu.factor_edits_note"))
            self._offer_factor_edit(key)
        else:
            self._say(_text("menu.not_applied") % (outcome.message or "refused"))

    def _offer_factor_edit(self, key: str) -> None:
        """The guided factor picker: a factor word plus a value, through
        the service (the edit vocabulary is built in ``app``, never here)."""
        factor = self._ask("menu.ask_factor")
        if not factor:
            return
        value = self._ask("menu.ask_factor_value")
        record_key = None
        if factor == "sequence":
            record_key = self._ask("menu.ask_record") or None
        self._report(
            self._services.variants.append_factor(
                key, factor, value, record_key=record_key
            )
        )

    def _edit_variant(self) -> None:
        key = self._ask("menu.ask_source")
        project = self._project()
        if project is None:
            return
        if not any(spec.key == key for spec in project.specs):
            self._say(_text("menu.export_unknown") % key)
            return
        self._offer_factor_edit(key)

    def _duplicate_variant(self) -> None:
        source = self._ask("menu.ask_source")
        new_key = self._ask("menu.ask_key")
        label = self._ask("menu.ask_label")
        outcome = self._services.variants.duplicate_spec(source, new_key, label or "")
        if outcome.ok:
            self._say(_text("menu.copied") % new_key)
        else:
            self._say(_text("menu.not_applied") % (outcome.message or "refused"))

    def _delete_variant(self) -> None:
        key = self._ask("menu.ask_source")
        if not self._confirm():
            return
        outcome = self._services.variants.remove_spec(key)
        if outcome.ok:
            self._say(_text("menu.removed") % key)
        else:
            self._say(_text("menu.not_applied") % (outcome.message or "refused"))

    def _preview_variant(self) -> None:
        key = self._ask("menu.ask_source")
        project = self._project()
        if project is None:
            return
        spec = next((s for s in project.specs if s.key == key), None)
        if spec is None:
            self._say(_text("menu.export_unknown") % key)
            return
        outcome = self._services.variants.preview(key)
        if not outcome.ok:
            self._say(_text("menu.not_applied") % (outcome.message or "failed"))
            return
        variant = outcome.variants[0]
        summary = _summary_of(variant.configuration)
        self._say(_banner(_text("menu.preview_header") + ": " + key, self._width))
        self._say(_text("menu.preview_name") % summary["job_name"])
        self._say(_text("menu.preview_seeds") % (summary["seed_values"],))
        self._say(_text("menu.preview_entities"))
        for record in variant.configuration.records:
            self._say(_entity_line(record))
        self._say(_text("menu.preview_modifications") % len(spec.edits))
        self._say(
            _text("menu.preview_output")
            % self._file_name_for(project.configuration.metadata.name, key)
        )
        answer = self._ask("menu.ask_show_json")
        if answer.lower() in ("y", "yes"):
            self._show_json(key)

    def _file_name_for(self, project_name: str, key: str) -> str:
        """The same naming function the export uses — imported through
        ``app``'s generation module (``ui`` never re-derives names)."""
        from configbuilder.app.generation_service import variant_file_name

        return variant_file_name(project_name, key)

    # -- export ------------------------------------------------------------------

    def _export_menu(self) -> None:
        from configbuilder.ui.present import format_findings

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
