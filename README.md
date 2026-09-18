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
| `GET` | `/health/ready` | banco e storage aptos para ingestão |
| `GET` | `/metrics` | métricas Prometheus da API |

As respostas e eventos nunca incluem binário, caminho físico, URL pública,
connection string ou credencial. O RabbitMQ e os exporters não participam da
readiness da API porque a outbox preserva eventos aceitos.

## Observabilidade

API e worker emitem logs JSON com `correlation_id`, `trace_id` e `span_id`.
O worker expõe métricas e saúde em `127.0.0.1:9001` por padrão. Traces ficam
desativados no modo simples; para exportar ao Tempo local, configure:

```dotenv
DOCPIPE_INGESTION_TRACES_ENABLED=true
DOCPIPE_INGESTION_TRACES_EXPORTER=otlp
DOCPIPE_INGESTION_OTLP_ENDPOINT=http://127.0.0.1:4318
```

Inicie somente a stack de observabilidade, sem as dependências do laboratório:

```bash
docker compose -f docker-compose.observability.yml \
  --profile observability up -d --wait
```

Prometheus fica em `127.0.0.1:9090`, Grafana em `127.0.0.1:3000` e Tempo
recebe OTLP HTTP em `127.0.0.1:4318`. O dashboard provisionado é
`DocPipe Ingestion Overview`. Para diagnóstico por correlação:

```bash
uv run python -m docpipe_ingestion.diagnostics CORRELATION_UUID
```

O utilitário é somente leitura e não imprime payload, nome de arquivo,
checksum ou chave de storage. Consulte `docs/OBSERVABILITY.md` para consultas,
catálogos e limitações.

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
DOCPIPE_OBSERVABILITY_INTEGRATION=1 uv run pytest -m observability
```

Os testes usam somente dados sintéticos. Consulte `docs/DESIGN.md` para as
garantias e limitações da outbox e do armazenamento.
