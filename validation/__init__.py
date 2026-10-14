"""Dataset validation entry point (SRS section 5).

``validate_dataset`` runs schema, foreign-key and business-rule checks and
returns a :class:`ValidationReport`.
"""
from __future__ import annotations

from .report import ValidationReport
from .schema import validate_schema
from .foreign_keys import validate_foreign_keys
from .business_rules import validate_business_rules

__all__ = ["ValidationReport", "validate_dataset"]


def validate_dataset(tables, expected_tables=None):
    report = ValidationReport()
    validate_schema(tables, report, expected_tables)
    validate_foreign_keys(tables, report)
    validate_business_rules(tables, report)
    return report
