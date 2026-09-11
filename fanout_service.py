"""HTTP entry point for developer notification fanout."""

from fastapi import FastAPI, HTTPException

from devtools_fanout import FanoutRequest, FanoutResult, fan_out
from infrai_queue import InfraiError, InfraiQueue, InfraiTransportError

app = FastAPI(title="Developer tools notification fanout")


@app.post("/notifications/fanout", response_model=FanoutResult)
def publish_notification(request: FanoutRequest) -> FanoutResult:
    try:
        return fan_out(request, InfraiQueue())
    except InfraiError as exc:
        status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(
            status_code=status,
            detail={"code": exc.code, "error": exc.detail},
        ) from exc
    except (InfraiTransportError, KeyError) as exc:
        raise HTTPException(status_code=503, detail="Notification delivery could not be completed") from exc
