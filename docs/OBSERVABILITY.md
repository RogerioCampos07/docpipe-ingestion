# Instrumentação do DocPipe Ingestion

Este documento descreve os sinais de telemetria emitidos pelo serviço. A
Etapa 7 foi concluída com a instrumentação da API e do worker, sem atribuir ao
`docpipe-ingestion` a operação de uma stack central de observabilidade.

## Responsabilidades deste repositório

O serviço mantém:

- logs estruturados;
- geração e propagação de `correlation_id`;
- inclusão de `trace_id` e `span_id` quando há span ativo;
- métricas da aplicação;
- instrumentação de traces;
- liveness e readiness;
- propagação de W3C Trace Context pela outbox e pelo RabbitMQ;
- configuração da instrumentação por variáveis de ambiente;
- testes dos sinais e da propagação de contexto;
- capacidade de exportar traces para um endpoint configurável.

A instrumentação não depende do backend que coleta, armazena, consulta ou
visualiza os sinais.

## Sinais e privacidade

Os logs são JSON e compartilham `correlation_id` com metadados e evento. O
`correlation_id` é o identificador funcional do fluxo; ele não é derivado do
trace e continua disponível quando tracing está desativado. Quando há span
ativo, os logs também incluem `trace_id` e `span_id`.

Logs, métricas e traces não contêm conteúdo, nome original, payload completo,
checksum, chave de storage, connection string, token ou caminho absoluto. Os
logs principais usam as operações `service.start`, `service.stop`,
`http.request`, `document.ingest` e `outbox.publish`. Categorias estáveis
distinguem falhas da API, validação, banco, storage e RabbitMQ.

## Métricas do serviço

A API expõe `/metrics` em sua porta. O worker expõe `/metrics`,
`/health/live` e `/health/ready` na porta configurada, `9001` por padrão. Os
registries são independentes.

Famílias principais:

- requisições HTTP e sua duração;
- uploads, documentos aceitos e bytes recebidos ou armazenados;
- duração, falhas e transações do banco;
- duração, bytes e falhas de storage;
- backlog, idade e eventos esgotados da outbox;
- tentativas, confirmações, falhas e duração da publicação;
- ciclos do worker e estado das dependências de readiness.

As rotas usam templates. UUIDs, nomes, mensagens de erro, URLs e chaves nunca
são labels. As métricas usam formato compatível com coleta pelo Prometheus,
mas o Prometheus não é uma dependência do serviço.

## Traces e propagação de contexto

FastAPI cria o span servidor. Spans manuais cobrem `document.ingest`,
`document.get`, `storage.upload`, `database.commit`,
`outbox.publish_attempt` e `rabbitmq.publish`. O carrier `traceparent` e o
`tracestate` opcional ficam em coluna privada da outbox e em headers AMQP; o
payload versionado de `document.received.v1` não muda. Eventos antigos sem
carrier iniciam novo trace.

Traces ficam desativados no modo simples. Para exportá-los por OTLP HTTP:

```dotenv
DOCPIPE_INGESTION_TRACES_ENABLED=true
DOCPIPE_INGESTION_TRACES_EXPORTER=otlp
DOCPIPE_INGESTION_OTLP_ENDPOINT=http://127.0.0.1:4318
```

O endpoint é configurável e pode pertencer a qualquer backend compatível
escolhido pelo operador. Falha de exporter não invalida a readiness da API,
pois a aceitação segura depende do banco e do storage. RabbitMQ também não
participa da readiness da API porque a outbox preserva os eventos aceitos.

## Diagnóstico local

1. Copie `X-Correlation-ID` da resposta.
2. Filtre os streams JSON da API e do worker por esse valor.
3. Se tracing estiver ativo, use o `trace_id` no backend configurado.
4. Compare as durações dos spans de storage, banco e RabbitMQ.
5. Execute `uv run python -m docpipe_ingestion.diagnostics UUID` para consultar
   estado, tentativas e categoria segura do último erro.

O utilitário é somente leitura e não imprime payload, nome de arquivo,
checksum ou chave de storage. Readiness é uma avaliação pontual e não garante
quota, espaço ou sucesso da gravação seguinte.

## Stack central de observabilidade

OpenTelemetry Collector, Prometheus, Grafana, Jaeger, Tempo, Loki, dashboards,
alertas e armazenamento central de métricas, logs e traces não são
responsabilidades permanentes deste repositório. A composição operacional e a
configuração central de coleta e visualização dos microsserviços também ficam
fora de seu escopo.

O repositório ainda contém o Compose, configurações e dashboard de Prometheus,
Grafana e Tempo criados na implementação original da Etapa 7. Esses arquivos
são remanescentes temporários: sua remoção física será feita em uma alteração
separada de código e infraestrutura. Eles não definem a arquitetura futura do
`docpipe-ingestion`; este documento registra o estado-alvo enquanto a remoção
ainda não ocorreu.

## Integração futura entre microsserviços

Os microsserviços do DocPipe serão mantidos em repositórios separados. Cada um
deverá produzir seus próprios logs estruturados, correlation IDs, métricas e
traces e permitir a exportação para endpoints configuráveis.

Um futuro repositório integrador ou de plataforma poderá consumir esses
sinais, compor os microsserviços e concentrar coleta, armazenamento,
visualização, dashboards, alertas e experimentos integrados. Esse repositório
ainda não existe como implementação aprovada, e sua arquitetura permanece
sujeita a avaliação.

Nos experimentos isolados da Etapa 9, devem ser usados somente os sinais e os
recursos estritamente necessários. Se um backend central for necessário para
um experimento integrado, ele deverá ser tratado no futuro escopo integrador,
sem reincorporá-lo à responsabilidade deste serviço.
