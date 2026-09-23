import pytest
from fastapi import status
from fastapi.testclient import TestClient

from docpipe_ingestion.api.app import create_app
from docpipe_ingestion.infrastructure.health import ReadinessChecker
from docpipe_ingestion.infrastructure.settings import Settings


def test_liveness_reports_process_is_alive() -> None:
    application = create_app(Settings(environment='test'))

    with TestClient(application) as client:
        response = client.get('/health/live')

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {'status': 'ok'}


def test_application_uses_configured_service_name() -> None:
    application = create_app(
        Settings(service_name='Configured Ingestion', environment='test')
    )

    assert application.title == 'Configured Ingestion'


def test_readiness_reports_only_stable_public_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        ReadinessChecker,
        'check',
        lambda self: {'database': False, 'storage': True},
    )
    application = create_app(Settings(environment='test'))

    with TestClient(application) as client:
        response = client.get('/health/ready')

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.json()['error']['code'] == 'service_not_ready'
    assert 'database' not in response.text
    assert 'storage' not in response.text


def test_readiness_is_independent_from_rabbitmq(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        ReadinessChecker,
        'check',
        lambda self: {'database': True, 'storage': True},
    )
    application = create_app(
        Settings(environment='test', rabbitmq_url='amqp://unavailable/private')
    )

    with TestClient(application) as client:
        response = client.get('/health/ready')

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {'status': 'ok'}


def test_disabling_metrics_preserves_liveness() -> None:
    application = create_app(Settings(metrics_enabled=False))
    with TestClient(application) as client:
        assert client.get('/metrics').status_code == status.HTTP_404_NOT_FOUND
        assert client.get('/health/live').status_code == status.HTTP_200_OK
