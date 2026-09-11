from typing import Any

from devtools_fanout import FanoutRequest, fan_out


class RecordingPublisher:
    def __init__(self) -> None:
        self.calls: list[tuple[dict[str, Any], str]] = []

    def publish(self, payload: dict[str, Any], idempotency_key: str) -> dict[str, Any]:
        self.calls.append((payload, idempotency_key))
        return {}


def test_warning_diagnostic_only_reaches_matching_severity_subscribers() -> None:
    request = FanoutRequest.model_validate(
        {
            "event": {
                "kind": "diagnostic",
                "event_id": "diag-204",
                "component": "type-checker",
                "severity": "warning",
                "message": "Generated declarations differ",
            },
            "subscribers": [
                {
                    "subscriber_id": "ide-panel",
                    "event_kinds": ["diagnostic"],
                    "minimum_diagnostic_severity": "info",
                },
                {
                    "subscriber_id": "release-pager",
                    "event_kinds": ["diagnostic", "release"],
                    "minimum_diagnostic_severity": "error",
                },
                {
                    "subscriber_id": "build-log",
                    "event_kinds": ["build"],
                },
            ],
        }
    )
    publisher = RecordingPublisher()

    result = fan_out(request, publisher)

    assert result.model_dump() == {"event_id": "diag-204", "published": 1, "skipped": 2}
    assert publisher.calls[0][0]["subscriber_id"] == "ide-panel"
    first_key = publisher.calls[0][1]
    publisher_again = RecordingPublisher()
    fan_out(request, publisher_again)
    assert publisher_again.calls[0][1] == first_key
