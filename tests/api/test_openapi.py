from fastapi.testclient import TestClient

from docpipe_ingestion.api.app import create_app
from docpipe_ingestion.infrastructure.settings import Settings


def test_openapi_documents_versioned_contract() -> None:
    application = create_app(Settings(environment='test'))

    with TestClient(application) as client:
        schema = client.get('/openapi.json').json()

    post = schema['paths']['/v1/documents']['post']
    get = schema['paths']['/v1/documents/{document_id}']['get']
    assert 'multipart/form-data' in post['requestBody']['content']
    assert set(post['responses']) == {'202', '400', '413', '415', '503'}
    assert set(get['responses']) == {'200', '400', '404', '503'}
    assert (
        'examples'
        in schema['components']['schemas']['DocumentAcceptedResponse']
    )
    assert 'examples' in schema['components']['schemas']['DocumentResponse']
