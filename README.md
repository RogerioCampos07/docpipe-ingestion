# DocPipe Ingestion

Microserviço de entrada de documentos do **DocPipe**, projeto acadêmico voltado ao estudo de desempenho, escalabilidade e observabilidade em uma arquitetura de microserviços.

## Responsabilidade

O Ingestion recebe documentos, valida a requisição, armazena o arquivo original, registra seus metadados e publica um evento para que o restante do pipeline continue de forma assíncrona.

Este serviço **não executa OCR**, não classifica documentos e não extrai dados de negócio.

## Fluxo principal

1. O cliente envia um documento.
2. A API valida formato, tamanho e metadados.
3. O arquivo original é salvo em `dataset/documents/` com nome gerado pelo
   serviço.
4. Os metadados e o estado inicial são persistidos no SQLite.
5. Um evento `document.received.v1` é publicado.
6. A API devolve `202 Accepted` com o identificador do documento.

## Escopo da primeira versão

- upload de um arquivo por requisição;
- formatos iniciais: PDF, PNG e JPEG;
- validação de tipo e limite de tamanho configurável;
- cálculo de checksum SHA-256;
- identificação única do documento;
- persistência de metadados e estado;
- armazenamento local do arquivo original em `dataset/documents/`;
- persistência dos metadados e da outbox em SQLite;
- publicação confiável do evento de recebimento;
- consulta de status pelo identificador;
- health checks, métricas, logs estruturados e traces;
- testes automatizados e teste de carga.

## Stack da primeira versão

- Python 3.14+
- FastAPI e Pydantic
- SQLAlchemy 2 e Alembic
- SQLite
- sistema de arquivos local em `dataset/documents/`
- broker assíncrono com adaptador, permitindo RabbitMQ no laboratório local e Azure Service Bus no ambiente Azure
- OpenTelemetry e Prometheus
- pytest e Locust
- Docker e Kubernetes/AKS

SQLite e o diretório local simplificam a primeira versão e os experimentos em
uma única instância. PostgreSQL e armazenamento de objetos permanecem como
evolução necessária antes de executar o serviço com múltiplas réplicas.

Os documentos recebidos e o arquivo SQLite são dados de execução e não devem
ser versionados no Git.

## Endpoints iniciais

| Método | Rota | Finalidade |
| --- | --- | --- |
| `POST` | `/v1/documents` | Receber um documento |
| `GET` | `/v1/documents/{document_id}` | Consultar metadados e estado |
| `GET` | `/health/live` | Verificar se o processo está ativo |
| `GET` | `/health/ready` | Verificar dependências essenciais |
| `GET` | `/metrics` | Expor métricas para Prometheus |

## Estados do documento

- `RECEIVED`: solicitação aceita e registrada;
- `STORED`: arquivo original persistido;
- `PUBLISHED`: evento entregue ao broker;
- `FAILED`: falha definitiva no fluxo de ingestão.

## Documentação do repositório

- [AGENTS.md](AGENTS.md): regras para agentes de código.
- [DESIGN.md](docs/DESIGN.md): arquitetura e decisões técnicas.
- [REQUIREMENTS.md](docs/REQUIREMENTS.md): requisitos e critérios de aceite.
- [PLAN.md](docs/PLAN.md): sequência incremental de implementação.

## Execução

Os comandos de instalação e execução serão acrescentados quando a estrutura mínima da aplicação for implementada. O gerenciador de dependências adotado é o `uv`.

## Status

Planejamento inicial. A implementação deve seguir as etapas de
[PLAN.md](docs/PLAN.md).
