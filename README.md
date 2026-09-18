# DocPipe Ingestion

Microserviço de entrada do DocPipe. Recebe PDF, PNG ou JPEG, valida e grava o
original por streaming, persiste metadados e uma outbox transacional e publica
`document.received.v1` no RabbitMQ. Não executa OCR, classificação ou extração.

## Modos locais

O modo simples é o padrão: SQLite em `dataset/docpipe-ingestion.db` e arquivos
privados em `dataset/documents/`. Ele não requer PostgreSQL nem Azurite. O
RabbitMQ só é necessário para executar o publicador da outbox.

O laboratório compartilhado usa PostgreSQL, Azurite Blob e RabbitMQ. O Azurite
é um emulador local da API do Azure Blob Storage e não requer conta, assinatura
ou recurso Azure. Ele não valida Managed Identity, RBAC, rede privada,
disponibilidade ou todas as características do Azure real.

| Banco | Storage | Uso |
| --- | --- | --- |
| SQLite | local | desenvolvimento e testes rápidos |
| PostgreSQL | local | banco compartilhado com arquivos locais |
| PostgreSQL | Azurite | laboratório compartilhado completo |
| SQLite | Azurite | composição suportada, ainda limitada a uma instância SQLite |

## Preparação

Requer Python 3.14, `uv` e Docker Compose.

```bash
uv sync --locked
cp .env.example .env
```

O `.env` é local e não deve ser versionado. Para o modo simples, preserve
`DOCPIPE_INGESTION_DATABASE_BACKEND=sqlite` e
`DOCPIPE_INGESTION_STORAGE_BACKEND=local`.

## Laboratório compartilhado

Configure no `.env`:

```dotenv
DOCPIPE_INGESTION_DATABASE_BACKEND=postgresql
DOCPIPE_INGESTION_DATABASE_URL=postgresql+psycopg://docpipe:docpipe-local@127.0.0.1:5432/docpipe_ingestion
DOCPIPE_INGESTION_STORAGE_BACKEND=azurite
DOCPIPE_INGESTION_BLOB_CONNECTION_STRING=DefaultEndpointsProtocol=http;AccountName=docpipe;AccountKey=ZG9jcGlwZS1sb2NhbC1vbmx5LW5vdC1zZWNyZXQ=;BlobEndpoint=http://127.0.0.1:10000/docpipe;
```

Inicie e confirme as dependências:

```bash
docker compose pull postgres rabbitmq azurite
docker compose up -d --wait postgres rabbitmq azurite
docker compose ps
```

Inicialize o schema e o container privado:

```bash
uv run alembic upgrade head
uv run python -m docpipe_ingestion.init_blob_storage
```

O PostgreSQL do laboratório pode começar vazio; não existe migração automática
dos dados do SQLite.

Execute API e worker em terminais separados:

```bash
uv run uvicorn docpipe_ingestion.api.app:app --host 127.0.0.1 --port 8000
uv run python -m docpipe_ingestion.outbox_worker
```

Dentro de outro container da rede Compose, use `postgres:5432`,
`rabbitmq:5672` e `http://azurite:10000/docpipe` nas configurações. Para uma
aplicação executada diretamente no SBX, use as portas publicadas em
`127.0.0.1`.

Ao terminar, preserve os volumes:

```bash
docker compose stop postgres rabbitmq azurite
```

## API

| Método | Rota | Resultado |
| --- | --- | --- |
| `POST` | `/v1/documents` | `202` após arquivo, documento e outbox seguros |
| `GET` | `/v1/documents/{document_id}` | metadados privados ou `404` |
| `GET` | `/health/live` | vida do processo |

As respostas e eventos nunca incluem binário, caminho físico, URL pública,
connection string ou credencial. Readiness, métricas e traces pertencem à
Etapa 7 e ainda não foram antecipados.

## Testes e qualidade

```bash
uv run task lint
uv run task format-check
uv run task typecheck
uv run pytest
uv run typos
```

Integrações reais são opt-in:

```bash
DOCPIPE_POSTGRESQL_INTEGRATION=1 uv run pytest -m postgresql
DOCPIPE_AZURITE_INTEGRATION=1 uv run pytest -m azurite
DOCPIPE_RABBITMQ_INTEGRATION=1 uv run pytest -m rabbitmq
DOCPIPE_STACK_INTEGRATION=1 uv run pytest -m stack
```

Os testes usam somente dados sintéticos. Consulte `docs/DESIGN.md` para as
garantias e limitações da outbox e do armazenamento.
