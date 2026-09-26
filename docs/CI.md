# Integração contínua

O workflow `.github/workflows/ci.yml` valida o `docpipe-ingestion` em pull
requests destinadas à `main`, pushes na `main` e execuções manuais. Ele usa
runners hospedados pelo GitHub e não publica imagens, cria releases ou faz
deploy.

## Checks

| Check | Responsabilidade |
| --- | --- |
| `ci-quality` | Ruff, formatação, mypy e typos |
| `ci-tests` | testes sem serviços, Compose, integrações reais e cobertura |
| `ci-image` | build da imagem e smoke test da API empacotada |

Os três nomes são os checks obrigatórios informados para a `main`.
Alterações apenas de documentação também
executam todos os checks, pois o workflow não possui filtros de caminhos.

## Reprodução local

Use Python e `uv` nas versões declaradas por `.python-version` e pelo
Dockerfile. Instale o ambiente sem atualizar o lockfile:

```bash
uv sync --locked --group dev
```

As verificações de qualidade equivalentes são:

```bash
uv run --locked task lint
uv run --locked task format-check
uv run --locked task typecheck
uv run --locked typos
```

Execute primeiro os testes que não usam serviços externos:

```bash
uv run --locked pytest \
  -m "not (postgresql or rabbitmq or azurite or stack)" \
  --cov=docpipe_ingestion --cov-report=
```

Para as integrações, use um projeto Compose isolado e descartável. Os destinos
abaixo devem apontar somente para serviços de teste, pois alguns testes limpam
tabelas e filas:

```bash
export COMPOSE_PROJECT_NAME=docpipe-ingestion-ci-local
docker compose --env-file /dev/null -f docker-compose.yml config --quiet
docker compose --env-file /dev/null -f docker-compose.yml \
  up -d --wait --wait-timeout 120 postgres rabbitmq azurite

export DOCPIPE_POSTGRESQL_INTEGRATION=1
export DOCPIPE_RABBITMQ_INTEGRATION=1
export DOCPIPE_AZURITE_INTEGRATION=1
export DOCPIPE_STACK_INTEGRATION=1
export DOCPIPE_INGESTION_TEST_POSTGRESQL_URL=\
'postgresql+psycopg://docpipe:docpipe-local@127.0.0.1:5432/docpipe_ingestion'
export DOCPIPE_INGESTION_TEST_AZURITE_CONNECTION_STRING=\
'DefaultEndpointsProtocol=http;AccountName=docpipe;AccountKey=ZG9jcGlwZS1sb2NhbC1vbmx5LW5vdC1zZWNyZXQ=;BlobEndpoint=http://127.0.0.1:10000/docpipe;'
export DOCPIPE_INGESTION_RABBITMQ_URL=\
'amqp://docpipe:docpipe@127.0.0.1:5672/docpipe'

uv run --locked pytest \
  -m "postgresql or rabbitmq or azurite or stack" \
  --cov=docpipe_ingestion --cov-append --cov-report= -ra -vv

docker compose --env-file /dev/null -f docker-compose.yml \
  down --volumes --remove-orphans
```

Use outro nome de projeto se `docpipe-ingestion-ci-local` já existir. Não use
o projeto ou os volumes persistentes do laboratório para executar os testes.
Os próprios testes aplicam migrations, criam containers privados no Azurite e
removem os objetos temporários que possuem.

O job `ci-tests` também valida somente a sintaxe das três variantes Compose
dos experimentos. Os testes rápidos em `tests/experiments/` verificam
contratos e proteções sem iniciar serviços. Locust, falhas controladas e
benchmarks permanecem manuais e não são checks de PR.

O build e a validação mínima da imagem usam o Dockerfile existente. O smoke
test do CI aplica migrations em um volume SQLite descartável, inicia o comando
padrão da imagem e exige sucesso em `/health/live`, `/health/ready` e
`/metrics`. Isso valida a API empacotada no modo simples; não valida o worker
em execução nem publica a imagem.

## Diagnóstico

Comece pelo primeiro passo que falhou no job. O job de testes preserva JUnit,
cobertura e, em falhas dos serviços, as últimas linhas dos logs de PostgreSQL,
RabbitMQ e Azurite. O job de imagem preserva o estado e as últimas linhas do
log da API quando o smoke test falha. Os artefatos ficam disponíveis por sete
dias e não incluem `.env`, volumes, documentos ou dumps do ambiente.

Uma integração não pode ficar verde por ausência de configuração: os opt-ins
e destinos são obrigatórios, e o relatório JUnit é rejeitado se estiver vazio,
tiver skips ou não contiver os seis testes externos esperados. A instrumentação
é testada com exporters em memória e falhas simuladas, sem Collector,
Prometheus, Grafana ou Tempo.

O cancelamento por concorrência substitui execuções antigas da mesma pull
request. O workflow usa somente permissão de leitura do conteúdo e não usa
segredos de produção, tokens pessoais ou `pull_request_target`.

## Limites

Validação local de YAML, testes, Compose e imagem não substitui a execução dos
jobs no GitHub. A Etapa 8 foi mergeada; os três checks acima devem continuar
com os mesmos nomes e escopo. O laboratório da Etapa 9 não executa carga nem
falhas controladas em PRs.

CI termina na validação e no build local da imagem. Publicação, release e
deploy continuam fora desta etapa. O Dockerfile atual ainda executa como root;
essa pendência permanece registrada para a revisão da Etapa 10.
