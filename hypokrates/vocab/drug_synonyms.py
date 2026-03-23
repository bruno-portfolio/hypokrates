"""INN / USAN drug name synonyms for query expansion.

FAERS stores names verbatim — "epinephrine" and "adrenaline" split the signal.
This dict enables merging across naming conventions until RxNorm programmatic
expansion replaces it.
"""

from __future__ import annotations

DRUG_SYNONYMS: dict[str, frozenset[str]] = {
    "EPINEPHRINE": frozenset({"ADRENALINE"}),
    "NOREPINEPHRINE": frozenset({"NORADRENALINE"}),
    "ACETAMINOPHEN": frozenset({"PARACETAMOL"}),
    "ALBUTEROL": frozenset({"SALBUTAMOL"}),
    "MEPERIDINE": frozenset({"PETHIDINE"}),
    "LIDOCAINE": frozenset({"LIGNOCAINE"}),
    "NITROGLYCERIN": frozenset({"GLYCERYL TRINITRATE"}),
    "CYCLOSPORINE": frozenset({"CICLOSPORIN", "CICLOSPORINE"}),
    "FUROSEMIDE": frozenset({"FRUSEMIDE"}),
    "PHENYLEPHRINE": frozenset({"NEOSYNEPHRINE"}),
    "SUCCINYLCHOLINE": frozenset({"SUXAMETHONIUM"}),
    "VECURONIUM": frozenset({"VECURONIUM BROMIDE"}),
    "ROCURONIUM": frozenset({"ROCURONIUM BROMIDE"}),
    "ATRACURIUM": frozenset({"ATRACURIUM BESYLATE"}),
    "CISATRACURIUM": frozenset({"CISATRACURIUM BESYLATE"}),
}

# Bidirectional lookup: name -> all OTHER names in the same group
_SYNONYM_MAP: dict[str, frozenset[str]] = {}
for _primary, _syns in DRUG_SYNONYMS.items():
    _all = frozenset({_primary}) | _syns
    for _name in _all:
        _SYNONYM_MAP[_name] = _all - {_name}


def expand_drug_names(name: str) -> list[str]:
    """Return [name] + all known synonyms (INN / USAN)."""
    upper = name.strip().upper()
    if upper in _SYNONYM_MAP:
        return [upper, *sorted(_SYNONYM_MAP[upper])]
    return [upper]
