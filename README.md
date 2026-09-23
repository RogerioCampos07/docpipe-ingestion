# DocPipe Ingestion

Microserviço de entrada do DocPipe. Recebe PDF, PNG ou JPEG, valida e grava o
original por streaming, persiste metadados e uma outbox transacional e publica
`document.received.v1` no RabbitMQ. Não executa OCR, classificação ou extração.

## Versões e estado do desenvolvimento

A versão em desenvolvimento é a `v1.0.0`. As Etapas 1 a 7 estão concluídas e
integradas à branch principal; as Etapas 8 a 10 permanecem planejadas. A
entrega `v1.0.0` será um laboratório completamente executável e reproduzível
em ambiente local, sem conta, assinatura ou recursos de cloud provider. Esse
laboratório não deve ser apresentado como ambiente de produção.

O escopo consolidado da `v1.0.0` inclui API FastAPI, SQLite e storage local no
modo simples; PostgreSQL, Azurite e RabbitMQ no laboratório compartilhado;
transactional outbox; API e worker separados; Docker Compose; logs
estruturados; correlation ID; métricas e instrumentação de traces; health
checks; testes automatizados; CI com GitHub Actions; testes locais de carga e
resiliência; evidências reproduzíveis para o TCC; revisão de segurança;
documentação operacional e a release `v1.0.0`. Kind, Kubernetes e uma stack
central de observabilidade não fazem parte do escopo desta versão.

Os microsserviços do DocPipe serão mantidos em repositórios separados, cada um
com código, testes, CI, imagem, health checks e instrumentação próprios. Um
futuro repositório integrador ou de plataforma poderá compor os serviços e a
observabilidade central. A separação de responsabilidades está aprovada;
esse repositório ainda não existe e sua implementação não está definida.

### Roadmap da `v1.1.0`

A `v1.1.0` fica reservada para implantação e integração Azure: AKS, Azure
Container Registry, Azure Database for PostgreSQL Flexible Server, Azure Blob
Storage real, Azure Key Vault, Managed Identity, RBAC, rede e endpoints
privados, ingress, domínio e TLS no Azure, infraestrutura como código, análise
FinOps, observabilidade gerenciada, políticas de backup, disponibilidade e
recuperação e validação da aplicação nesse ambiente. A possível troca de
RabbitMQ por Azure Service Bus será avaliada
futuramente e não é uma decisão confirmada.

## Modos locais

O modo simples é o padrão: SQLite em `dataset/docpipe-ingestion.db` e arquivos
privados em `dataset/documents/`. Ele não requer PostgreSQL nem Azurite. O
RabbitMQ só é necessário para executar o publicador da outbox.

O laboratório compartilhado usa PostgreSQL, Azurite Blob e RabbitMQ. O Azurite
é um emulador local da API do Azure Blob Storage e não requer conta, assinatura
ou recurso Azure. Ele não valida Managed Identity, RBAC, rede privada,
disponibilidade ou todas as características do Azure real.

Compatibilidade de API não significa equivalência completa: a `v1.0.0` não é
implantada nem validada no Azure Blob Storage real ou em qualquer outro
serviço Azure.

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
| `GET` | `/metrics` | métricas da API em formato compatível com Prometheus |

As respostas e eventos nunca incluem binário, caminho físico, URL pública,
connection string ou credencial. O RabbitMQ e os exporters não participam da
readiness da API porque a outbox preserva eventos aceitos.

## Instrumentação e telemetria

API e worker emitem logs JSON com `correlation_id`, `trace_id` e `span_id`.
O worker expõe métricas e saúde em `127.0.0.1:9001` por padrão. No modo simples,
a exportação e a instrumentação automática HTTP ficam desativadas; spans
manuais e contexto local podem existir. Para exportar por OTLP a um endpoint
configurado, use:

```dotenv
DOCPIPE_INGESTION_TRACES_ENABLED=true
DOCPIPE_INGESTION_TRACES_EXPORTER=otlp
DOCPIPE_INGESTION_OTLP_ENDPOINT=http://127.0.0.1:4318
```

O endpoint pode ser fornecido por uma ferramenta escolhida pelo operador. O
serviço não depende de um backend específico para coletar, armazenar, consultar
ou visualizar os sinais. Para diagnóstico por correlação:

```bash
uv run python -m docpipe_ingestion.diagnostics CORRELATION_UUID
```

O utilitário é somente leitura e não imprime payload, nome de arquivo,
checksum ou chave de storage. Consulte `docs/OBSERVABILITY.md` para consultas,
catálogos e limitações.

Este repositório mantém a instrumentação, sem hospedar uma stack central.
O Compose contém somente PostgreSQL, RabbitMQ e Azurite. Logs são emitidos
em stderr, métricas são consultadas nos endpoints locais e traces podem ser
exportados para um endpoint OTLP HTTP externo. A exportação fica desabilitada
com `DOCPIPE_INGESTION_TRACES_ENABLED=false` e
`DOCPIPE_INGESTION_TRACES_EXPORTER=none`.

A retirada da infraestrutura central foi uma refatoração preparatória à
Etapa 8; a instrumentação da Etapa 7 permanece. A referência histórica para
recuperar as configurações está em `docs/OBSERVABILITY.md`.

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

Os testes de instrumentação integram a suíte padrão e usam exporters em
memória e simulações, sem Collector. A configuração dos testes ignora o
`.env` e neutraliza variáveis da aplicação e do SDK antes da coleta. Testes
que verificam configuração podem definir suas próprias variáveis.

Execute integrações somente em um projeto Compose isolado, com dados
descartáveis: alguns testes limpam tabelas e filas. Configure explicitamente
`DOCPIPE_INGESTION_TEST_POSTGRESQL_URL` e
`DOCPIPE_INGESTION_TEST_AZURITE_CONNECTION_STRING` para os recursos de teste.
Nas integrações RabbitMQ e de stack, configure
`DOCPIPE_INGESTION_RABBITMQ_URL`; essa variável é preservada quando o opt-in
correspondente está ativo. A opção `--env-file` do Compose não exporta essas
variáveis para o processo pytest.

Os testes usam somente dados sintéticos. Consulte `docs/DESIGN.md` para as
garantias e limitações da outbox e do armazenamento.
