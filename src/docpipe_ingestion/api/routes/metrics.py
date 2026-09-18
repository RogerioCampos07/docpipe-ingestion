from fastapi import APIRouter, Request, Response, status
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from docpipe_ingestion.infrastructure.observability.metrics import Metrics

router = APIRouter(tags=['observability'])


@router.get('/metrics', include_in_schema=False)
def metrics(request: Request) -> Response:
    if not request.app.state.settings.metrics_enabled:
        return Response(status_code=status.HTTP_404_NOT_FOUND)
    current: Metrics = request.app.state.metrics
    try:
        statistics = request.app.state.service_provider.outbox_statistics()
    except Exception:
        pass
    else:
        current.outbox_pending.set(statistics.pending)
        current.outbox_exhausted.set(statistics.exhausted)
        current.outbox_oldest_age.set(statistics.oldest_age_seconds)
    return Response(
        generate_latest(current.registry), media_type=CONTENT_TYPE_LATEST
    )
