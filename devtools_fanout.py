"""Domain models and fanout decision for developer-tools notifications."""

from __future__ import annotations

import hashlib
from enum import IntEnum
from typing import Annotated, Literal, Protocol

from pydantic import BaseModel, Field


class Severity(IntEnum):
    info = 10
    warning = 20
    error = 30

    @classmethod
    def _missing_(cls, value: object) -> "Severity | None":
        """Allow the human-readable names used by the REST payloads."""
        if isinstance(value, str):
            try:
                return cls[value.lower()]
            except KeyError:
                return None
        return None


class BuildEvent(BaseModel):
    kind: Literal["build"]
    event_id: str
    repository: str
    commit_sha: str
    status: Literal["started", "passed", "failed"]


class ReleaseOperation(BaseModel):
    kind: Literal["release"]
    event_id: str
    service: str
    version: str
    operation: Literal["deploy", "promote", "rollback"]


class Diagnostic(BaseModel):
    kind: Literal["diagnostic"]
    event_id: str
    component: str
    severity: Severity
    message: str


DeveloperEvent = Annotated[
    BuildEvent | ReleaseOperation | Diagnostic,
    Field(discriminator="kind"),
]


class Subscriber(BaseModel):
    subscriber_id: str
    event_kinds: set[Literal["build", "release", "diagnostic"]]
    minimum_diagnostic_severity: Severity = Severity.info


class FanoutRequest(BaseModel):
    event: DeveloperEvent
    subscribers: list[Subscriber]


class FanoutResult(BaseModel):
    event_id: str
    published: int
    skipped: int


class Publisher(Protocol):
    def publish(self, payload: dict[str, object], idempotency_key: str) -> dict[str, object]:
        """Publish one subscriber delivery."""
        return {}


def should_notify(subscriber: Subscriber, event: DeveloperEvent) -> bool:
    if event.kind not in subscriber.event_kinds:
        return False
    if isinstance(event, Diagnostic):
        return event.severity >= subscriber.minimum_diagnostic_severity
    return True


def fan_out(request: FanoutRequest, publisher: Publisher) -> FanoutResult:
    published = 0
    for subscriber in request.subscribers:
        if not should_notify(subscriber, request.event):
            continue
        key_source = f"{request.event.event_id}:{subscriber.subscriber_id}"
        key = hashlib.sha256(key_source.encode("utf-8")).hexdigest()
        publisher.publish(
            payload={
                "subscriber_id": subscriber.subscriber_id,
                "event": request.event.model_dump(mode="json"),
            },
            idempotency_key=key,
        )
        published += 1
    return FanoutResult(
        event_id=request.event.event_id,
        published=published,
        skipped=len(request.subscribers) - published,
    )
