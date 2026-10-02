# Integração contínua

O workflow `.github/workflows/ci.yml` valida o `docpipe-ingestion` em pull
requests destinadas à `main`, pushes na `main` e execuções manuais. Ele usa
runners hospedados pelo GitHub e não publica imagens, cria releases ou faz
deploy.

O workflow mantém os checks `ci-quality`, `ci-tests` e `ci-image`. A Etapa 9
ampliou `ci-image` para validar a aplicação empacotada com a infraestrutura
operacional local. A auditoria 10a confirma a execução dos três jobs no GitHub
Actions para `7e48d5f` e registra o alcance em `docs/RELEASE_AUDIT.md`.
Resultados locais de outra revisão não substituem esses jobs. A 10b deve
verificar os checks novamente se alterar a candidata.

## Checks

| Check | Responsabilidade |
| --- | --- |
| `ci-quality` | Ruff, formatação, mypy e typos |
| `ci-tests` | testes sem serviços, Compose, integrações reais e cobertura |
| `ci-image` | build da imagem e fluxo funcional HTTP com API e worker empacotados |

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
  -m "not (postgresql or rabbitmq or azurite or stack or packaged)" \
  --cov=docpipe_ingestion --cov-report=
```

Para as integrações, use um projeto Compose isolado e descartável. Os destinos
abaixo devem apontar somente para serviços de teste, pois alguns testes limpam
tabelas e filas:

```bash
export COMPOSE_PROJECT_NAME=docpipe-ingestion-ci-local
docker compose --env-file /dev/null -f docker-compose.yml config --quiet
docker compose --env-file /dev/null -f docker-compose.yml \
  up -d --wait --wait-timeout 120 postgres azurite
docker compose --env-file /dev/null -f docker-compose.yml \
  up -d --wait --wait-timeout 150 rabbitmq

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
contratos e proteções sem iniciar serviços. O workflow manual
`phase-9-smoke.yml` e os scripts experimentais permanecem preservados, com
nomes históricos. Ensaios experimentais de carga e resiliência não são checks
de PR nem requisitos de fechamento. Isso não exclui os testes funcionais de
falha e retomada previstos nos contratos.

O `ci-image` constrói a imagem uma vez, valida a configuração Compose, inicia
PostgreSQL, Azurite e RabbitMQ em projeto isolado, aplica migrations e prepara
o container privado de blobs por um serviço de setup executado da imagem. Em
seguida inicia a API empacotada e executa `tests/integration/test_packaged_compose.py`
como harness no runner. O harness chama a API por HTTP, verifica o worker
separado, consulta os serviços reais e executa os comandos operacionais de
reenvio e reconciliação através da imagem Compose. Nenhum container da
aplicação recebe mount do checkout. O harness Python e seus clientes externos
executam no runner; o código da aplicação validado executa na imagem construída.

Para reproduzir esse check localmente, use valores exclusivos para projeto e
portas e execute os comandos no shell de desenvolvimento:

```bash
export CI_IMAGE=docpipe-ingestion:ci-local
export DOCPIPE_INGESTION_IMAGE="$CI_IMAGE"
export CI_COMPOSE_PROJECT=docpipe-ci-image-local
export CI_API_URL=http://127.0.0.1:18000
export API_PORT=18000 WORKER_METRICS_PORT=19001
export POSTGRES_PORT=25432 RABBITMQ_PORT=25672
export RABBITMQ_MANAGEMENT_PORT=25673 AZURITE_BLOB_PORT=20000
export DOCPIPE_PACKAGED_IMAGE_INTEGRATION=1
export DOCPIPE_INGESTION_INCOMPLETE_FILE_AGE_SECONDS=1
export DOCPIPE_INGESTION_TEST_POSTGRESQL_URL=\
  postgresql+psycopg://docpipe:docpipe-local@127.0.0.1:25432/docpipe_ingestion
export DOCPIPE_INGESTION_TEST_AZURITE_CONNECTION_STRING=\
  'DefaultEndpointsProtocol=http;AccountName=docpipe;AccountKey=ZG9jcGlwZS1sb2NhbC1vbmx5LW5vdC1zZWNyZXQ=;BlobEndpoint=http://127.0.0.1:20000/docpipe;'
export DOCPIPE_INGESTION_RABBITMQ_URL=\
  amqp://docpipe:docpipe@127.0.0.1:25672/docpipe

docker build --tag "$CI_IMAGE" .
docker compose --project-name "$CI_COMPOSE_PROJECT" \
  --env-file /dev/null -f docker-compose.yml config --quiet
docker compose --project-name "$CI_COMPOSE_PROJECT" \
  --env-file /dev/null -f docker-compose.yml \
  up -d --no-build --wait --wait-timeout 120 postgres azurite
docker compose --project-name "$CI_COMPOSE_PROJECT" \
  --env-file /dev/null -f docker-compose.yml \
  up -d --no-build --wait --wait-timeout 150 rabbitmq
docker compose --project-name "$CI_COMPOSE_PROJECT" \
  --env-file /dev/null -f docker-compose.yml \
  --profile setup run --rm setup
docker compose --project-name "$CI_COMPOSE_PROJECT" \
  --env-file /dev/null -f docker-compose.yml \
  up -d --no-build --wait --wait-timeout 120 api
uv run --locked pytest -m packaged \
  --junitxml=packaged-compose.xml -ra -vv
uv run --locked python .github/scripts/verify_pytest_junit.py \
  packaged-compose.xml \
  --require-module tests.integration.test_packaged_compose=1
docker compose --project-name "$CI_COMPOSE_PROJECT" \
  --env-file /dev/null -f docker-compose.yml down --volumes --remove-orphans
docker image rm "$CI_IMAGE"
```

Esse procedimento é destrutivo somente para o projeto e a imagem explicitamente
nomeados como descartáveis. Se falhar antes da limpeza, colete `ps --all` e os
logs dos serviços desse projeto antes de removê-lo. Não reutilize projeto ou
volumes de desenvolvimento.

## Diagnóstico

Comece pelo primeiro passo que falhou no job. O job de testes preserva JUnit,
cobertura e, em falhas dos serviços, as últimas linhas dos logs de PostgreSQL,
RabbitMQ e Azurite. O job de imagem preserva JUnit, estado do projeto e logs
dos serviços, API e worker. Os artefatos ficam disponíveis por sete dias; os
volumes e documentos de teste não são publicados.

Uma integração não pode ficar verde por ausência de configuração: os opt-ins
e destinos são obrigatórios, e o relatório JUnit é rejeitado se estiver vazio,
tiver skips ou não contiver os seis testes externos esperados. A instrumentação
é testada com exporters em memória e falhas simuladas, sem Collector,
Prometheus, Grafana ou Tempo.

O cancelamento por concorrência substitui execuções antigas da mesma pull
request. O workflow usa somente permissão de leitura do conteúdo e não usa
segredos de produção, tokens pessoais ou `pull_request_target`.

## Limites e divisão das etapas

Validação local de YAML, testes, Compose e imagem não substitui a execução dos
jobs no GitHub Actions para uma revisão candidata. Os três checks preservam
seus nomes e proteções; `ci-tests` mantém cobertura e integrações reais, e os
relatórios JUnit rejeitam ausência, vazio, falhas, erros, skips e módulos
obrigatórios ausentes. `ci-image` exige seu próprio relatório e o teste
empacotado obrigatório.

Na Etapa 9, `ci-image` e a prova integrada exercitam a imagem construída no
Compose oficial: migrations em PostgreSQL vazio, blobs privados no Azurite,
API por HTTP, worker separado, publicação, falha parcial, reenvio, retomada,
reconciliação e persistência após reinício. O harness e os clientes de
verificação rodam no runner, enquanto API, worker e comandos de operação rodam
da imagem, sem mounts do checkout.

A Etapa 10 revisa as evidências, confirma que pertencem à versão candidata e
prepara o aceite local da `v1.0.0`. Esse aceite não depende de conta,
infraestrutura ou validação Azure; Azure pertence à `v1.1.0`. Experimentos
completos serão planejados somente após validação funcional Azure e não
bloqueiam a versão local. CI não publica imagens, release ou deploy; commit,
push, PR, merge, tag e publicação seguem o fluxo manual e as autorizações
aplicáveis.

## Verificação de alterações somente documentais

Executar `git diff --check` e revisar coerência, referências locais e escopo
dos arquivos alterados. A configuração atual de typos exclui `*.md` em
`.typos.toml`; seu sucesso não valida a redação Markdown. Não há tarefa
específica de lint Markdown configurada. Não instalar ferramentas nem iniciar
serviços para uma revisão restrita à documentação.
