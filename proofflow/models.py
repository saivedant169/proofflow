"""Portable immutable records used by the ProofFlow execution runtime."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


class ProofFlowError(RuntimeError):
    """A failure that must not be converted into a valid cached answer."""


class MissingEvidenceError(ProofFlowError):
    pass


class InvalidInputError(ProofFlowError):
    pass


class DependencyCycleError(ProofFlowError):
    pass


@dataclass(frozen=True)
class ArtifactRecord:
    id: str
    kind: str
    logical_id: str
    content_hash: str
    created_at: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SourceChange:
    logical_id: str
    previous_id: str | None
    current_id: str
    changed: bool


@dataclass(frozen=True)
class Currentness:
    artifact_id: str
    state: str
    reasons: tuple[dict[str, Any], ...] = ()

    @property
    def is_current(self) -> bool:
        return self.state == "current"


@dataclass(frozen=True)
class RefreshResult:
    replacements: dict[str, str]
    executed: tuple[str, ...]
    reused: tuple[str, ...]
    elapsed_ms: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
