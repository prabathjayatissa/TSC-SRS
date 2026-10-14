"""Validation primitives shared by the validation rule modules."""
from __future__ import annotations


class ValidationReport:
    """Accumulates validation issues for a dataset."""

    def __init__(self):
        self.issues = []

    def add(self, level, table, key, message):
        self.issues.append(dict(level=level, table=table, key=key, message=message))
        return self

    def error(self, table, key, message):
        return self.add("error", table, key, message)

    def warning(self, table, key, message):
        return self.add("warning", table, key, message)

    @property
    def errors(self):
        return [i for i in self.issues if i["level"] == "error"]

    @property
    def warnings(self):
        return [i for i in self.issues if i["level"] == "warning"]

    @property
    def ok(self):
        return not self.errors

    def to_dict(self):
        return dict(
            ok=self.ok,
            error_count=len(self.errors),
            warning_count=len(self.warnings),
            issues=self.issues,
        )

    def format(self):
        if not self.issues:
            return "validation passed with no issues"
        lines = [f"  [{i['level']}] {i['table']} {i['key']}: {i['message']}"
                 for i in self.issues]
        return "\n".join(lines)
