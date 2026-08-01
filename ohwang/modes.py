from __future__ import annotations

from enum import Enum


class Mode(str, Enum):
    DEFAULT = "default"
    PLAN = "plan"
    AUTO = "auto"
    BYPASS = "bypass"

    @property
    def label(self) -> str:
        return self.value.upper()
