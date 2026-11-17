"""Conservative English and Portuguese plural normalization for retrieval."""

import unicodedata


def normalize_token(token: str) -> str:
    decomposed = unicodedata.normalize("NFKD", token.casefold())
    word = "".join(char for char in decomposed if not unicodedata.combining(char))
    singular = _singular(word)
    match singular:
        case value if len(value) > 4 and value.endswith(("a", "o")):
            return value[:-1]
        case _:
            return singular


def _singular(word: str) -> str:
    match word:
        case value if len(value) > 4 and value.endswith("ies"):
            return value[:-3] + "y"
        case value if len(value) > 4 and value.endswith(("oes", "aos")):
            return value[:-3] + "ao"
        case value if len(value) > 4 and value.endswith(
            ("sses", "xes", "zes", "ches", "shes")
        ):
            return value[:-2]
        case value if (
            len(value) > 4
            and value.endswith("s")
            and not value.endswith(("ss", "us", "is"))
        ):
            return value[:-1]
        case _:
            return word
