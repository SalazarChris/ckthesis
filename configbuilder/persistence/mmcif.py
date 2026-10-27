"""Template mmCIF structure reading — the file half of a template definition.

A protein template is one external mmCIF file plus the user's own 0-based
``query:template`` index pairs. The pairs are validated in
``configbuilder/app/reference_validation.py``; this module answers the other
question a template raises, at the moment its file is chosen: *is this file a
structure at all?* A file that cannot be read as mmCIF is refused there, so a
broken template is never attached to a record and never serialised.

Two checks, strongest first, because the builder runs on the standard library
alone (plan §4) and an optional component may strengthen a check but is never
required for one (§9.6):

1. **gemmi**, the established mmCIF library, when it is importable
   (``pyproject.toml``'s ``templates`` extra installs it). A file it cannot
   parse is not a structure. Its absence is not a failure: the check below
   still runs, so the guarantee does not depend on it.
2. **The bundled lexical scan**, always. mmCIF's own lexical grammar: a
   ``data_`` block, quoted values and ``;`` text fields, a value for every
   data item, and every ``loop_`` row holding exactly as many values as the
   loop declares tags — the defect that makes a truncated file unusable. It
   also requires at least one structural category, so a text file that merely
   contains a ``data_`` line is not mistaken for a structure.

The two tiers are deliberately in agreement on those defects: the bundled
scan applies the same rules the parser names, so whether gemmi happens to be
installed does not change the verdict on a committed fixture. Installing it
can only add strictness for input neither tier has seen.

Neither check makes a mapping biologically correct: the indices are the
user's, and the template's own residues are never read here. What the checks
establish is only that AF3 has a structure to read.

Reading belongs to this layer (plan §5.3 rule 8: filesystem access is confined
to ``output`` and ``persistence``), so ``app`` asks this module instead of
opening the file itself.
"""

from __future__ import annotations

from typing import Optional

__all__ = ["library_available", "structure_problem", "template_structure_problem"]

# The categories that make a file a structural template. A file with a
# ``data_`` block but none of these is not one.
_STRUCTURE_PREFIXES = (
    "_atom_site.",
    "_entity_poly",
    "_struct_asym",
    "_entity.",
    "_pdbx_poly_seq_scheme",
)

_NO_STRUCTURE = (
    "the file is not an mmCIF structure "
    "(it has no _atom_site, _entity_poly, _struct_asym or _entity records)"
)
_NO_BLOCK = "the file is not an mmCIF structure (it has no 'data_' block)"


def structure_problem(text: str) -> Optional[str]:
    """Why ``text`` is not a usable template structure, or ``None`` when it is.

    The bundled lexical scan runs first (it is cheap and deterministic), then
    the established parser when one is installed — an installed parser can only
    add strictness, never turn a refusal into an acceptance.
    """
    problem = _lexical_problem(text)
    if problem is not None:
        return problem
    return _library_problem(text)


def template_structure_problem(path: str) -> Optional[str]:
    """Why the file at ``path`` is not a usable template, or ``None``.

    The reasons are clauses the caller embeds in its own sentence, and they
    keep the project's existing vocabulary: an unreadable file, an empty one,
    text that is not UTF-8, and text that is not a structure.
    """
    try:
        with open(path, "rb") as handle:
            payload = handle.read()
    except OSError:
        return "the file cannot be read"
    if not payload.strip():
        return "the file is empty"
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        return "the file is not UTF-8 text"
    return structure_problem(text)


# -- the established parser, when it is installed (plan §9.6) --------------------


_LOADED = False
_LIBRARY = None


def _load_library():
    """gemmi, or ``None`` when it is not importable (patched by tests).

    A separate function so the bundled path can be exercised deliberately, and
    so the import is attempted once per process.
    """
    try:
        import gemmi
    except Exception:  # not installed, or broken: either way, unavailable
        return None
    return gemmi


def _library():
    global _LOADED, _LIBRARY
    if not _LOADED:
        _LIBRARY = _load_library()
        _LOADED = True
    return _LIBRARY


def library_available() -> bool:
    """Whether an established mmCIF parser is importable in this environment."""
    return _library() is not None


def _library_problem(text: str) -> Optional[str]:
    """The established parser's verdict on ``text``, or ``None``.

    ``None`` means either "it parsed" or "there is no parser here"; the
    bundled scan has already had its say in both cases.
    """
    module = _library()
    if module is None:
        return None
    try:
        document = module.cif.read_string(text)
    except Exception as error:  # the library's own way of saying no
        return "the file is not a readable mmCIF structure (%s)" % _reason(error)
    try:
        has_block = any(True for _block in document)
    except Exception:
        # A library whose iteration fails has not told us the file is broken;
        # the bundled scan's verdict stands.
        return None
    if not has_block:
        return _NO_BLOCK
    return None


def _reason(error) -> str:
    """One short line from a parser refusal — never a traceback in the UI."""
    lines = [line.strip() for line in str(error).splitlines() if line.strip()]
    first = lines[0] if lines else error.__class__.__name__
    return first[:160]


# -- the bundled lexical scan, always -------------------------------------------


def _lexical_problem(text: str) -> Optional[str]:
    """mmCIF's lexical grammar, and the structure it must contain."""
    scan = _Scan()
    return scan.run(text)


def _tokens(line: str):
    """One line's tokens: whitespace-separated, with quotes grouping.

    An mmCIF quoted value ends at the end of its line, so an unterminated
    quote simply ends the value there. A ``#`` outside quotes starts a comment
    that runs to the end of the line.
    """
    tokens = []
    length = len(line)
    index = 0
    while index < length:
        character = line[index]
        if character.isspace():
            index += 1
            continue
        if character == "#":
            break
        if character in "'\"":
            index += 1
            start = index
            while index < length and line[index] != character:
                index += 1
            tokens.append(line[start:index])
            index += 1
            continue
        start = index
        while index < length and not line[index].isspace():
            index += 1
        tokens.append(line[start:index])
    return tokens


class _Scan:
    """One pass over the text, stopping at the first defect it can name."""

    def __init__(self) -> None:
        self._block = False
        self._structure = False
        self._in_loop = False
        self._tags = ()
        self._values = 0
        self._loop_line = 0

    def _end_loop(self) -> Optional[str]:
        """Apply the loop rule: complete rows of exactly the declared width."""
        tagged = len(self._tags)
        self._in_loop = False
        if tagged and self._values % tagged:
            problem = (
                "the file is not a usable mmCIF structure (the loop starting at "
                "line %d declares %d tags, and its values do not form complete "
                "rows of that size)" % (self._loop_line, tagged)
            )
            self._tags = ()
            self._values = 0
            return problem
        self._tags = ()
        self._values = 0
        return None

    def _start_loop(self, line_number: int) -> None:
        self._in_loop = True
        self._tags = ()
        self._values = 0
        self._loop_line = line_number

    def _note_tag(self, token: str) -> None:
        if token.startswith(_STRUCTURE_PREFIXES):
            self._structure = True

    @staticmethod
    def _text_field_follows(lines, index: int) -> bool:
        """Whether the next meaningful line opens a ``;`` text field.

        A data item's value may sit on the following line only as a text
        field, which begins with ``;`` at column 0. Anything else after a tag
        that carries no value is the parser's own complaint ("has no value").
        """
        total = len(lines)
        while index < total:
            line = lines[index]
            if not line.strip() or line.lstrip().startswith("#"):
                index += 1
                continue
            return line.startswith(";")
        return False

    def run(self, text: str) -> Optional[str]:
        lines = text.splitlines()
        total = len(lines)
        index = 0
        while index < total:
            raw = lines[index]
            number = index + 1
            index += 1
            if not raw.strip() or raw.lstrip().startswith("#"):
                continue
            if raw.startswith(";"):
                # A ';' text field: one value, from column 0 to the next ';'
                # at column 0. It may contain anything, '#' included.
                while index < total and not lines[index].startswith(";"):
                    index += 1
                index += 1
                if self._in_loop:
                    self._values += 1
                continue
            tokens = _tokens(raw)
            if not tokens:
                continue
            first = tokens[0]
            if first == "loop_":
                problem = self._end_loop()
                if problem is not None:
                    return problem
                self._start_loop(number)
                continue
            if first.startswith("data_") or first.startswith("save_") or first == "stop_":
                problem = self._end_loop()
                if problem is not None:
                    return problem
                if first.startswith("data_"):
                    self._block = True
                continue
            if first.startswith("_"):
                if self._in_loop:
                    if self._values:
                        # A tag after values ends the loop; the row rule is
                        # applied before this tag is read as a data item.
                        problem = self._end_loop()
                        if problem is not None:
                            return problem
                    else:
                        self._tags += tuple(tokens)
                        for token in tokens:
                            self._note_tag(token)
                        continue
                self._note_tag(first)
                if len(tokens) > 1 or self._text_field_follows(lines, index):
                    continue
                return (
                    "the file is not a usable mmCIF structure (the data item %s "
                    "at line %d has no value)" % (first, number)
                )
            if self._in_loop:
                self._values += len(tokens)
            # A bare value outside a loop is tolerated: this scan rejects what
            # cannot be a structure, it does not grade mmCIF style.
        problem = self._end_loop()
        if problem is not None:
            return problem
        if not self._block:
            return _NO_BLOCK
        if not self._structure:
            return _NO_STRUCTURE
        return None
