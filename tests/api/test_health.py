from fastapi import status
from fastapi.testclient import TestClient

from docpipe_ingestion.api.app import create_app
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
