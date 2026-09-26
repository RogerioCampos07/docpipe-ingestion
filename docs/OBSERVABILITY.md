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

`DOCPIPE_INGESTION_METRICS_ENABLED=false` faz `/metrics` da API responder
`404`. O worker controla seu servidor completo por
`DOCPIPE_INGESTION_WORKER_MONITORING_ENABLED`; enquanto habilitado, seus três
endpoints permanecem disponíveis. Host e porta são configurados por
`DOCPIPE_INGESTION_WORKER_METRICS_HOST` e
`DOCPIPE_INGESTION_WORKER_METRICS_PORT`.

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

A exportação e a instrumentação automática HTTP ficam desativadas no modo
simples. Spans manuais e contexto local ainda podem existir, inclusive
`trace_id` em logs. Para exportar traces por OTLP HTTP:

```dotenv
DOCPIPE_INGESTION_TRACES_ENABLED=true
DOCPIPE_INGESTION_TRACES_EXPORTER=otlp
DOCPIPE_INGESTION_OTLP_ENDPOINT=http://127.0.0.1:4318
```

O endpoint é uma URL base: o serviço acrescenta `/v1/traces`. Ele pode
pertencer a qualquer receptor compatível escolhido pelo operador e não
pressupõe um Collector local. Falha de exporter não invalida a readiness da API,
pois a aceitação segura depende do banco e do storage. RabbitMQ também não
participa da readiness da API porque a outbox preserva os eventos aceitos.

Para desabilitar exportação, use
`DOCPIPE_INGESTION_TRACES_ENABLED=false` e
`DOCPIPE_INGESTION_TRACES_EXPORTER=none`. Habilitar traces com exporter `none`
é um erro de configuração, rejeitado na inicialização. Os exporters não
participam da readiness do worker; banco e conexão/canal RabbitMQ participam.
O worker precisa conectar ao broker na inicialização. Essas falhas funcionais
não devem ser confundidas com indisponibilidade do receptor OTLP.

Logs JSON são emitidos em stderr, controlados por
`DOCPIPE_INGESTION_LOG_FORMAT` e `DOCPIPE_INGESTION_LOG_LEVEL`. Métricas são
expostas para scrape; somente traces possuem exportação OTLP configurada pela
aplicação. Os pacotes OpenTelemetry e `prometheus-client` pertencem ao serviço.

### Limites de exportação e encerramento

`DOCPIPE_INGESTION_TRACES_SAMPLER` seleciona `always_on`, `always_off` ou
`parentbased_traceidratio`; neste último, a razão de novos traces é definida
por `DOCPIPE_INGESTION_TRACES_SAMPLE_RATIO`. O protocolo suportado por
`DOCPIPE_INGESTION_OTLP_PROTOCOL` é `http/protobuf`.

O envio usa `BatchSpanProcessor`, com uma thread de exportação e fila finita.
No SDK fixado pelo lockfile, os padrões são 2.048 spans na fila, lotes de 512
e intervalo de 5 segundos. As variáveis padrão do SDK
`OTEL_BSP_MAX_QUEUE_SIZE`, `OTEL_BSP_MAX_EXPORT_BATCH_SIZE` e
`OTEL_BSP_SCHEDULE_DELAY` permitem ajuste; evite valores que ampliem a memória
além do orçamento local. Uma fila cheia descarta spans antigos. Isso não é
uma fila durável nem uma garantia de retenção de toda a telemetria.

`DOCPIPE_INGESTION_OTLP_TIMEOUT_SECONDS` configura o timeout do exporter,
com padrão de 2 segundos. O exporter aplica retry finito e backoff dentro de
seu orçamento; chamadas de transporte e agendamento podem ultrapassar esse
tempo, que não representa um deadline absoluto do processo. Não use
`OTEL_BSP_EXPORT_TIMEOUT` como garantia de cancelamento: o processador da
versão atual não aplica esse limite à chamada de exportação.

`DOCPIPE_INGESTION_TELEMETRY_SHUTDOWN_TIMEOUT_SECONDS`, padrão de 3 segundos,
limita a espera da aplicação pelo encerramento da telemetria. Uma única
thread daemon de limpeza por provider é iniciada antecipadamente para também
atender `atexit`. Chamadas repetidas compartilham o mesmo prazo. A limpeza
pode continuar em segundo plano após o prazo, mas não impede o processo de
terminar. Um aviso seguro registra o timeout; spans pendentes podem ser
perdidos. Os timeouts das dependências funcionais são independentes.

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

O Compose, as configurações e o dashboard centrais de Prometheus, Grafana e
Tempo foram removidos na refatoração preparatória à Etapa 8. A instrumentação
do serviço permanece. A retirada de declarações não remove containers,
imagens, redes ou volumes de instalações anteriores.

### Referência histórica

O commit `38f3fa7d71a646c85b777e05184dc3c6a6f1ec7b` contém as configurações
anteriores à remoção. Para consultá-las sem modificar o working tree:

```bash
git ls-tree -r --name-only 38f3fa7 -- observability/
git show 38f3fa7:docker-compose.observability.yml
```

Esses caminhos são históricos, não instruções para iniciar uma stack atual.
Uma recuperação deve selecionar os arquivos ou reverter a mudança específica,
preservando alterações posteriores e sem reset destrutivo. Não há cópias
arquivadas dessas configurações na árvore atual.

## Integração futura entre microsserviços

Os microsserviços do DocPipe serão mantidos em repositórios separados. Cada um
deverá produzir seus próprios logs estruturados, correlation IDs, métricas e
traces e permitir a exportação para endpoints configuráveis.

Um futuro repositório integrador ou de plataforma poderá consumir esses
sinais, compor os microsserviços e concentrar coleta, armazenamento,
visualização, dashboards, alertas e experimentos integrados. Esse repositório
ainda não existe e sua arquitetura permanece sujeita a avaliação. A separação
de responsabilidades está aprovada; isso não define sua implementação.

Nos experimentos isolados da Etapa 9, devem ser usados somente os sinais e os
recursos estritamente necessários. Se um backend central for necessário para
um experimento integrado, ele deverá ser tratado no futuro escopo integrador,
sem reincorporá-lo à responsabilidade deste serviço.

O laboratório em `docs/EXPERIMENTS.md` coleta `/metrics` de cada processo,
logs estruturados e snapshots de leitura do banco. O gauge de backlog da API
é atualizado durante a consulta a `/metrics` e pode conservar o último valor
se o banco estiver indisponível. O worker tem registry independente; gauges
de duas APIs não devem ser somados. `published_at` recebe o horário do início
da tentativa posteriormente confirmada, portanto sua diferença para
`created_at` é apenas aproximação do tempo até a publicação. A exportação
OTLP permanece opcional; sem receptor não há armazenamento de spans completos.
