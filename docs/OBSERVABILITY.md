# Observabilidade do DocPipe Ingestion

Esta documentação descreve a observabilidade já implementada na Etapa 7. Na
`v1.0.0`, toda a telemetria permanece local e a stack pode ser ativada sob
demanda também dentro do laboratório Kind. Integração com serviços Azure fica
no backlog da `v1.1.0`; Azure Monitor e Application Insights não fazem parte
da versão atual e só poderão ser adotados após aprovação.

## Sinais e privacidade

Os logs são JSON e compartilham `correlation_id` com metadados e evento. Quando
há span ativo, também incluem `trace_id` e `span_id`. Logs, métricas e traces
não contêm conteúdo, nome original, payload completo, checksum, storage key,
connection string, token ou caminho absoluto.

Os logs principais usam as operações `service.start`, `service.stop`,
`http.request`, `document.ingest` e `outbox.publish`. Falhas usam categorias
estáveis para distinguir API, validação, banco, storage e RabbitMQ.

## Métricas

A API expõe `/metrics` em sua porta. O worker expõe `/metrics`,
`/health/live` e `/health/ready` na porta configurada, `9001` por padrão.
Os registries são independentes.

Famílias principais:

- `docpipe_ingestion_http_requests_total` e
  `docpipe_ingestion_http_request_duration_seconds`;
- `docpipe_ingestion_uploads_total`,
  `docpipe_ingestion_documents_accepted_total` e bytes recebidos/armazenados;
- duração, falhas e transações do banco;
- duração, bytes e falhas de storage;
- backlog, idade e eventos esgotados da outbox;
- tentativas, confirmações, falhas e duração da publicação;
- ciclos do worker e estado das dependências de readiness.

Rotas usam templates. UUIDs, nomes, mensagens de erro, URLs e chaves nunca são
labels.

## Traces

FastAPI cria o span servidor. Spans manuais cobrem `document.ingest`,
`document.get`, `storage.upload`, `database.commit`,
`outbox.publish_attempt` e `rabbitmq.publish`. O carrier `traceparent` e o
`tracestate` opcional ficam em coluna privada da outbox e em headers AMQP; o
payload versionado não muda. Eventos antigos sem carrier iniciam novo trace.

## Diagnóstico

1. Copie `X-Correlation-ID` da resposta.
2. Filtre os streams JSON da API e worker por esse valor.
3. Use o `trace_id` encontrado para abrir o trace no Explore do Grafana/Tempo.
4. Compare durações dos spans de storage, banco e RabbitMQ.
5. Execute `uv run python -m docpipe_ingestion.diagnostics UUID` para consultar
   estado, tentativas e categoria segura do último erro.

Consultas PromQL úteis:

```promql
sum by (route) (rate(docpipe_ingestion_http_requests_total[5m]))
```

```promql
histogram_quantile(0.95,
  sum by (le, route)
    (rate(docpipe_ingestion_http_request_duration_seconds_bucket[5m])))
```

```promql
max(docpipe_ingestion_outbox_pending_events)
```

```promql
max(docpipe_ingestion_outbox_oldest_pending_age_seconds)
```

```promql
sum by (error_category)
  (rate(docpipe_ingestion_outbox_publication_failures_total[5m]))
```

Nenhuma consulta define alerta, SLO ou limite de desempenho. Esses valores
dependem do baseline da Etapa 9.

## Stack local

O Compose opcional usa profiles e rede do host, adequada ao laboratório Linux:

```bash
docker compose -f docker-compose.observability.yml \
  --profile observability up -d --wait
docker compose -f docker-compose.observability.yml ps
docker compose -f docker-compose.observability.yml \
  --profile observability stop
```

Prometheus e Grafana podem ser iniciados com `--profile metrics`; Tempo com
`--profile traces`. A stack tem limites somados de 896 MiB e retenção local de
24 horas. A coleta de logs centralizada não faz parte da stack mínima; logs
continuam nos streams JSON dos processos.

Readiness é uma avaliação pontual e não garante quota, espaço ou sucesso da
gravação seguinte. O worker informa vida do servidor de monitoramento; falhas
do broker continuam visíveis nos logs e métricas e não invalidam a readiness
da API.

Na Etapa 8, esta mesma stack será disponibilizada no Kind somente quando
necessária, respeitando os recursos conservadores do laboratório. A forma de
execução no Kind não transforma o ambiente local em produção nem demonstra
equivalência com observabilidade gerenciada no Azure.
