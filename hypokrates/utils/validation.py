"""Validação de inputs."""

from __future__ import annotations

import re

from hypokrates.exceptions import ValidationError

_DRUG_NAME_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9 \t\-\.]+$")
_MAX_DRUG_NAME_LENGTH = 200


def validate_drug_name(name: str) -> str:
    """Valida e normaliza nome de medicamento.

    Raises:
        ValidationError: Se o nome for inválido.

    Returns:
        Nome normalizado (stripped).
    """
    name = name.strip()
    if not name:
        raise ValidationError("Drug name cannot be empty")
    if len(name) > _MAX_DRUG_NAME_LENGTH:
        raise ValidationError(f"Drug name too long (max {_MAX_DRUG_NAME_LENGTH} chars)")
    if not _DRUG_NAME_PATTERN.match(name):
        raise ValidationError(
            f"Invalid drug name: {name!r}. "
            "Only letters, numbers, spaces, hyphens, and dots are allowed."
        )
    return name
