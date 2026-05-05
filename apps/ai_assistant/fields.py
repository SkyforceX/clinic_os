from __future__ import annotations

from django.db import models


class VectorField(models.Field):
    """
    Historical field kept only so old ai_assistant migrations can still be imported.
    Runtime knowledge models now live in apps.ai_knowledge.
    """

    description = "PostgreSQL pgvector field"

    def __init__(self, *args, dimensions: int, **kwargs):
        self.dimensions = int(dimensions)
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        kwargs["dimensions"] = self.dimensions
        return name, path, args, kwargs

    def db_type(self, connection):
        return f"vector({self.dimensions})"

    def get_internal_type(self):
        return "TextField"

    def get_placeholder(self, value, compiler, connection):
        if getattr(connection, "vendor", "") == "postgresql":
            return "%s::vector"
        return "%s"

    def from_db_value(self, value, expression, connection):
        return self.to_python(value)

    def to_python(self, value):
        if value in (None, ""):
            return None
        if isinstance(value, list):
            return [float(item) for item in value]
        if isinstance(value, tuple):
            return [float(item) for item in value]
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return None
            if stripped[0] == "[" and stripped[-1] == "]":
                body = stripped[1:-1].strip()
                if not body:
                    return []
                return [float(part.strip()) for part in body.split(",")]
        raise TypeError(f"Unsupported vector value: {type(value)!r}")

    def get_prep_value(self, value):
        if value in (None, ""):
            return None
        vector = self.to_python(value)
        if vector is None:
            return None
        return "[" + ",".join(self._format_item(item) for item in vector) + "]"

    @staticmethod
    def _format_item(value):
        return format(float(value), ".15g")
