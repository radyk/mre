"""Remediation catalog package (handoff §1).

Frozen authored knowledge (``remediation-catalog-v1.yaml``) + its typed models.
"""
from mre.catalog.models import (
    FallbackNote,
    RemediationCatalog,
    RemediationNote,
    load_catalog,
)

__all__ = [
    "FallbackNote",
    "RemediationCatalog",
    "RemediationNote",
    "load_catalog",
]
