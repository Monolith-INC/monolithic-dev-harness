"""The single declared contract for capability payload shapes.

``manifest.json`` speaks JSON Schema because ``input_schema`` is handed verbatim
to MCP clients as ``inputSchema``. JSON Schema is deliberately permissive about
how one constraint may be spelled: ``type`` is a name or a list of names, and
``additionalProperties`` is a schema whose two degenerate instances are spelled
as the booleans ``true`` (accept every extra key) and ``false`` (accept none).

That ambiguity stops here. Raw schema JSON is parsed exactly once, in this
module, into the algebraic types below; every other module consumes the parsed
contract and never inspects a raw schema again. Adding a second reader of the
raw shape is what previously let one manifest crash discovery, silently drop a
capability, and answer the same question three different ways.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .exhaustive import assert_never
from .state import FrozenDict, deep_freeze


class JsonType(Enum):
    """The JSON Schema primitive types the orchestrator constrains."""

    STRING = "string"
    BOOLEAN = "boolean"
    NUMBER = "number"
    INTEGER = "integer"
    OBJECT = "object"
    ARRAY = "array"
    NULL = "null"


_PREDICATES: Mapping[JsonType, Callable[[Any], bool]] = {
    JsonType.STRING: lambda value: isinstance(value, str),
    JsonType.BOOLEAN: lambda value: isinstance(value, bool),
    JsonType.NUMBER: lambda value: (
        isinstance(value, (int, float)) and not isinstance(value, bool)
    ),
    JsonType.INTEGER: lambda value: (
        isinstance(value, int) and not isinstance(value, bool)
    ),
    JsonType.OBJECT: lambda value: isinstance(value, dict),
    JsonType.ARRAY: lambda value: isinstance(value, list),
    JsonType.NULL: lambda value: value is None,
}

_ARTICLES: Mapping[JsonType, str] = {
    JsonType.INTEGER: "an",
    JsonType.OBJECT: "an",
    JsonType.ARRAY: "an",
}


# --- What a value's type must satisfy -------------------------------------


@dataclass(frozen=True)
class AnyType:
    """The value's type is not constrained."""


@dataclass(frozen=True)
class OneOfTypes:
    """The value must match one of ``types``, which is never empty."""

    types: frozenset[JsonType]


TypeContract = AnyType | OneOfTypes


# --- What keys outside `properties` must satisfy --------------------------


@dataclass(frozen=True)
class AcceptExtras:
    """Undeclared keys are permitted and unchecked (JSON Schema ``true``)."""


@dataclass(frozen=True)
class RejectExtras:
    """Undeclared keys are a violation (JSON Schema ``false``)."""


@dataclass(frozen=True)
class ConstrainExtras:
    """Undeclared keys are permitted but must satisfy ``contract``."""

    contract: TypeContract


ExtraProperties = AcceptExtras | RejectExtras | ConstrainExtras


# --- What a whole payload must satisfy ------------------------------------


@dataclass(frozen=True)
class Unconstrained:
    """No declared contract: any payload is accepted.

    Produced by an absent schema and by a schema whose top-level type is not
    ``object``. The orchestrator only constrains object-shaped payloads.
    """


@dataclass(frozen=True)
class ObjectContract:
    """A declared object payload contract."""

    properties: Mapping[str, TypeContract] = field(default_factory=FrozenDict)
    required: tuple[str, ...] = ()
    extras: ExtraProperties = AcceptExtras()

    def __post_init__(self) -> None:
        object.__setattr__(self, "properties", FrozenDict(self.properties))
        object.__setattr__(self, "required", tuple(self.required))


ValueContract = Unconstrained | ObjectContract


# --- How a violation is worded --------------------------------------------


@dataclass(frozen=True)
class Subject:
    """Wording for one payload direction; presentation only, never a rule."""

    missing_noun: str
    unknown_noun: str
    label: str
    use_article: bool


ARGUMENT = Subject(
    missing_noun="argument",
    unknown_noun="argument",
    label="Argument",
    use_article=False,
)
OUTPUT_PROPERTY = Subject(
    missing_noun="output property",
    unknown_noun="output property",
    label="Property",
    use_article=True,
)


# --- Parsing ---------------------------------------------------------------


@dataclass(frozen=True)
class ContractDiagnostic:
    """One reason a raw schema could not be parsed into a contract."""

    code: str
    message: str


@dataclass(frozen=True)
class Parsed:
    contract: ValueContract


@dataclass(frozen=True)
class Rejected:
    diagnostics: tuple[ContractDiagnostic, ...]


ParseResult = Parsed | Rejected


@dataclass(frozen=True)
class _Absent:
    """The key was not in the document, as distinct from an explicit JSON null.

    `dict.get` collapses those two, so `"type": null` used to read as "no type
    declared" and a malformed schema was accepted with an unconstrained
    contract, then handed to clients as though it were valid.
    """


_ABSENT = _Absent()


@dataclass(frozen=True)
class _TypeParsed:
    contract: TypeContract


@dataclass(frozen=True)
class _TypeRejected:
    raw: Any


_TypeParse = _TypeParsed | _TypeRejected


def _parse_type(raw: Any) -> _TypeParse:
    """Parse a JSON Schema ``type``: absent, one name, or a list of names.

    An absent key leaves the type unconstrained. Any present value that is not a
    name or a list of names -- including an explicit JSON null -- is rejected.
    """
    if isinstance(raw, _Absent):
        return _TypeParsed(AnyType())
    names = (raw,) if isinstance(raw, str) else raw
    if not isinstance(names, (list, tuple)) or not names:
        return _TypeRejected(raw)
    if not all(isinstance(name, str) for name in names):
        return _TypeRejected(raw)
    try:
        return _TypeParsed(OneOfTypes(frozenset(JsonType(name) for name in names)))
    except ValueError:
        return _TypeRejected(raw)


def _parse_properties(
    raw: Any, field_name: str
) -> tuple[Mapping[str, TypeContract], tuple[ContractDiagnostic, ...]]:
    if not isinstance(raw, dict):
        return FrozenDict(), (
            ContractDiagnostic(
                "invalid_properties", f"{field_name}.properties must be an object."
            ),
        )

    parsed: dict[str, TypeContract] = {}
    diagnostics: tuple[ContractDiagnostic, ...] = ()
    for name, property_schema in raw.items():
        if not isinstance(name, str) or not name:
            diagnostics += (
                ContractDiagnostic(
                    "invalid_property_name",
                    f"{field_name} property names must be non-empty strings.",
                ),
            )
            continue
        if not isinstance(property_schema, dict):
            diagnostics += (
                ContractDiagnostic(
                    "invalid_property_schema",
                    f"{field_name}.properties.{name} must be an object.",
                ),
            )
            continue
        match _parse_type(property_schema.get("type", _ABSENT)):
            case _TypeParsed(contract):
                parsed[name] = contract
            case _TypeRejected(raw_type):
                diagnostics += (
                    ContractDiagnostic(
                        "unsupported_property_type",
                        f"{field_name}.properties.{name}.type '{raw_type}' is not supported.",
                    ),
                )
            case _ as unmatched:
                assert_never(unmatched)

    return FrozenDict(parsed), diagnostics


def _parse_extras(
    raw: Any, field_name: str
) -> tuple[ExtraProperties, tuple[ContractDiagnostic, ...]]:
    """Parse ``additionalProperties``, normalizing its boolean sugar away."""
    invalid = (
        ContractDiagnostic(
            "invalid_additional_properties",
            f"{field_name}.additionalProperties must be a boolean or a schema object.",
        ),
    )
    if raw is None or raw is True:
        return AcceptExtras(), ()
    if raw is False:
        return RejectExtras(), ()
    if not isinstance(raw, dict):
        return AcceptExtras(), invalid
    match _parse_type(raw.get("type", _ABSENT)):
        case _TypeParsed(contract):
            return ConstrainExtras(contract), ()
        case _TypeRejected():
            return AcceptExtras(), invalid
        case _ as unmatched:
            assert_never(unmatched)


def _parse_required(
    raw: Any, field_name: str
) -> tuple[tuple[str, ...], tuple[ContractDiagnostic, ...]]:
    if not isinstance(raw, list) or not all(
        isinstance(item, str) and item for item in raw
    ):
        return (), (
            ContractDiagnostic(
                "invalid_required",
                f"{field_name}.required must be a list of non-empty strings.",
            ),
        )
    return tuple(dict.fromkeys(raw)), ()


def parse_value_contract(raw: Any, field_name: str) -> ParseResult:
    """Parse one raw schema into the single contract every consumer reads."""
    if raw is None or raw == {}:
        return Parsed(Unconstrained())
    if not isinstance(raw, dict):
        return Rejected(
            (
                ContractDiagnostic(
                    "schema_not_object", f"{field_name} must be an object."
                ),
            )
        )

    diagnostics: tuple[ContractDiagnostic, ...] = ()

    schema_type = _parse_type(raw.get("type", JsonType.OBJECT.value))
    match schema_type:
        case _TypeParsed(contract):
            top_level = contract
        case _TypeRejected(raw_type):
            top_level = AnyType()
            diagnostics += (
                ContractDiagnostic(
                    "unsupported_schema_type",
                    f"{field_name}.type '{raw_type}' is not supported.",
                ),
            )
        case _ as unmatched:
            assert_never(unmatched)

    required, required_diagnostics = _parse_required(
        raw.get("required", []), field_name
    )
    properties, property_diagnostics = _parse_properties(
        raw.get("properties", {}), field_name
    )
    extras, extras_diagnostics = _parse_extras(
        raw.get("additionalProperties"), field_name
    )
    diagnostics += required_diagnostics + property_diagnostics + extras_diagnostics

    if diagnostics:
        return Rejected(diagnostics)

    if not _constrains_objects(top_level):
        return Parsed(Unconstrained())
    return Parsed(
        ObjectContract(properties=properties, required=required, extras=extras)
    )


def _constrains_objects(contract: TypeContract) -> bool:
    match contract:
        case AnyType():
            return False
        case OneOfTypes(types):
            return types == frozenset({JsonType.OBJECT})
        case _ as unmatched:
            assert_never(unmatched)


# --- Checking --------------------------------------------------------------


def check_value(
    value: Any,
    contract: ValueContract,
    subject: Subject,
    *,
    not_object_message: str,
) -> tuple[str, ...]:
    """Check one payload against its contract. Pure and total."""
    match contract:
        case Unconstrained():
            return ()
        case ObjectContract() as object_contract:
            if not isinstance(value, dict):
                return (not_object_message,)
            return check_object(value, object_contract, subject)
        case _ as unmatched:
            assert_never(unmatched)


def check_object(
    value: Mapping[str, Any], contract: ObjectContract, subject: Subject
) -> tuple[str, ...]:
    missing = tuple(
        f"Missing required {subject.missing_noun} '{key}'."
        for key in contract.required
        if key not in value
    )
    present = tuple(
        critique
        for key, item in value.items()
        for critique in _check_member(key, item, contract, subject)
    )
    return missing + present


def _check_member(
    key: str, value: Any, contract: ObjectContract, subject: Subject
) -> tuple[str, ...]:
    declared = contract.properties.get(key)
    if declared is not None:
        return _check_type(key, value, declared, subject)

    match contract.extras:
        case AcceptExtras():
            return ()
        case RejectExtras():
            return (f"Unknown {subject.unknown_noun} '{key}' is not allowed.",)
        case ConstrainExtras(extra_contract):
            return _check_type(key, value, extra_contract, subject)
        case _ as unmatched:
            assert_never(unmatched)


def _check_type(
    key: str, value: Any, contract: TypeContract, subject: Subject
) -> tuple[str, ...]:
    match contract:
        case AnyType():
            return ()
        case OneOfTypes(types):
            if any(_PREDICATES[expected](value) for expected in types):
                return ()
            return (
                f"{subject.label} '{key}' should be {_expected_phrase(types, subject)}, "
                f"got {type(value).__name__}.",
            )
        case _ as unmatched:
            assert_never(unmatched)


def _expected_phrase(types: frozenset[JsonType], subject: Subject) -> str:
    names = tuple(sorted(expected.value for expected in types))
    if len(names) == 1:
        return _with_article(names[0], subject)
    return "one of " + ", ".join(names)


def _with_article(name: str, subject: Subject) -> str:
    if not subject.use_article:
        return name
    return f"{_ARTICLES.get(JsonType(name), 'a')} {name}"


# --- What counts as progress between attempts ------------------------------


@dataclass(frozen=True)
class WholeProduct:
    """No declared output fields, so every value the handler returned counts."""

    values: Mapping[str, Any] = field(default_factory=FrozenDict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "values", deep_freeze(self.values))


@dataclass(frozen=True)
class DeclaredFields:
    """Only the fields the manifest committed to in its output signature."""

    values: Mapping[str, Any] = field(default_factory=FrozenDict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "values", deep_freeze(self.values))


ProgressSignature = WholeProduct | DeclaredFields


def progress_signature(
    product: Mapping[str, Any], contract: ValueContract
) -> ProgressSignature:
    """Project a result onto the fields that can evidence progress.

    Comparing whole results made stall detection depend on handlers keeping
    non-progress data out of them -- an invariant nothing enforced, and the same
    failure mode as the field denylist it replaced: one incidental value that
    differs per attempt silently disables the check.

    A manifest that declares an output signature has already said which fields
    carry its result, so that declaration is the basis. A manifest that declares
    nothing -- or that names only fields this result does not carry -- gives no
    basis to narrow, and keeps the conservative whole-result comparison: an
    undetected stall wastes a retry budget, while a wrongly detected one halts
    work that was still moving.
    """
    match contract:
        case Unconstrained():
            return WholeProduct(product)
        case ObjectContract(properties, required, _):
            declared = frozenset(properties) | frozenset(required)
            present = {key: value for key, value in product.items() if key in declared}
            if not present:
                # The contract named nothing this result actually carries, so it
                # offers no basis to narrow by -- same position as no contract.
                return WholeProduct(product)
            return DeclaredFields(present)
        case _ as unmatched:
            assert_never(unmatched)
