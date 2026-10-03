# DocPipe Ingestion

Microserviço de entrada do DocPipe. Recebe PDF, PNG ou JPEG, valida e grava o
original por streaming, persiste metadados e uma outbox transacional e publica
`document.received.v1` no RabbitMQ. Não executa OCR, classificação ou extração.

Receber, registrar e armazenar documentos constitui uma capacidade de negócio
própria do Ingestion. O serviço permite consultar os metadados e o estado da
ingestão sem exigir Processing ou a conclusão de etapas posteriores. O `202`
confirma armazenamento e persistência de documento e outbox; `PUBLISHED`
registra a publicação confirmada pelo broker, sem aguardar um consumidor.
A outbox transacional e a entrega pelo menos uma vez permanecem obrigatórias.

Todos os microsserviços atuais e futuros do DocPipe devem ser desacoplados,
independentes e possuir utilidade própria. As fronteiras e proibições estão
em [DESIGN.md](docs/DESIGN.md#19-autonomia-obrigatória-dos-microsserviços), e
os critérios verificáveis no RNF-009 de [REQUIREMENTS.md](docs/REQUIREMENTS.md).
A auditoria anterior concluiu, por inspeção estática, que o Ingestion atende
à diretriz e não precisa de refatoração. Naquela auditoria não foram executados
testes nem validação operacional; a conclusão não comprova autonomia em
execução nem encerra a Etapa 9.

## Versões e estado do desenvolvimento

A versão em desenvolvimento é a `v1.0.0`. A implementação da Etapa 9 foi
mergeada e os três checks de CI passaram na revisão `7e48d5f`. A auditoria
10a classificou as provas funcionais e registrou pendências obrigatórias em
[RELEASE_AUDIT.md](docs/RELEASE_AUDIT.md). A 10b fechará essas pendências,
validará a candidata final e preparará o aceite local. Os critérios de
fechamento permanecem em [PLAN.md](docs/PLAN.md).

A `v1.0.0` entregará o serviço completo, autônomo e validado em ambiente
local/portátil com Docker Compose, PostgreSQL como banco próprio, Azurite para
blobs privados e RabbitMQ para mensageria. Inclui API FastAPI e worker
separados, transactional outbox, logs estruturados, correlation ID, métricas,
traces, health checks, testes automatizados, CI, revisão de segurança,
evidências funcionais e documentação operacional e de contratos.

A entrega não requer conta, assinatura ou recursos de cloud provider e não
deve ser apresentada como implantação de produção. Kind, Kubernetes,
observabilidade central e ensaios experimentais de carga ou resiliência não
integram seu fechamento. Os critérios e procedimentos estão em
[PLAN.md](docs/PLAN.md); não haverá uma etapa adicional para concluir a versão.
Atos de Git, tag e publicação de release exigem autorização específica.

Cada microsserviço deve manter repositório, domínio, banco de dados, migrations,
configuração, testes e CI próprios, além de imagem, health checks e
instrumentação. Sua evolução e implantação devem ser independentes, com
compatibilidade dos contratos públicos e versionados. Um
futuro repositório integrador ou de plataforma poderá compor os serviços e a
observabilidade central. A separação de responsabilidades está aprovada;
esse repositório ainda não existe e sua implementação não está definida.

### Roadmap da `v1.1.0`

A `v1.1.0` entregará suporte aos produtos e serviços Azure, incluindo Blob
Storage e PostgreSQL, preservando a compatibilidade dos contratos públicos.
Sua implementação será planejada posteriormente. A possível troca de
RabbitMQ por Azure Service Bus não é uma decisão confirmada.

O planejamento de carga e resiliência ocorrerá somente após a validação
funcional nesse ambiente Azure com Blob Storage e PostgreSQL. Scripts,
workflows e evidências históricos permanecem preservados.

## Implementação atual e configuração de entrega

O modo operacional agora usa PostgreSQL e Azurite por padrão, sem fallback
silencioso para SQLite ou armazenamento local. SQLite e o adaptador local
permanecem explícitos nas fixtures e testes auxiliares, sem representar suporte
a dois bancos operacionais.

PostgreSQL já possui driver `psycopg[binary]`, engine SQLAlchemy, migrations
Alembic, testes em `tests/integration/test_postgresql.py` e serviço com volume
em `docker-compose.yml`. Azurite e RabbitMQ também possuem adaptadores e testes.
Essas são evidências de implementação, não resultados de execução atual.

O Compose principal inclui PostgreSQL, Azurite, RabbitMQ, preparação controlada,
API e worker separados. A imagem executa como usuário não-root. A prova
`packaged` executou com sucesso para a revisão auditada no GitHub Actions;
o alcance e as pendências de cenários específicos estão no relatório 10a. O
pacote, o lockfile e o OpenAPI declaram `1.0.0` após o alinhamento inicial da
10b. As demais pendências da candidata permanecem na auditoria.

Banco, RabbitMQ e armazenamento são dependências legítimas de infraestrutura;
independência entre microsserviços não significa ausência dessas dependências.
O publicador requer RabbitMQ disponível e sua topologia de entrega, mas não
exige consumidores em execução. A ausência de consumidores não deve impedir
o aceite de documentos nem tornar a saúde dependente de outro microsserviço.

O laboratório compartilhado usa PostgreSQL, Azurite Blob e RabbitMQ. O Azurite
é um emulador local da API do Azure Blob Storage e não requer conta, assinatura
ou recurso Azure. Ele não valida Managed Identity, RBAC, rede privada,
disponibilidade ou todas as características do Azure real.

Compatibilidade de API não significa equivalência completa: a `v1.0.0` não é
implantada nem validada no Azure Blob Storage real ou em qualquer outro
serviço Azure.

## Execução local com Docker Compose

O Compose oficial executa toda a aplicação sem Processing nem outros
microsserviços. A configuração `.env.example` usa credenciais locais de
desenvolvimento, não destinadas a ambientes compartilhados ou de produção.
Copie o exemplo e inicie a infraestrutura:

```bash
uv sync --locked --group dev
cp .env.example .env
```

O `.env` é local e não deve ser versionado. As variáveis de portas e contas
locais estão descritas no `.env.example`. Suba PostgreSQL, Azurite e RabbitMQ,
aguardando seus health checks:

```bash
docker compose pull postgres rabbitmq azurite
docker compose up -d --wait postgres azurite
docker compose up -d --wait rabbitmq
docker compose ps
```

Execute migrations e prepare o container privado de blobs pelo serviço de
setup, que usa a mesma imagem da API e do worker:

```bash
docker compose --profile setup run --build --rm setup
```

O PostgreSQL pode começar vazio. Aplicar migrations cria/evolui o schema;
não existe transferência automática de dados SQLite nem necessidade presumida
de realizá-la. Preserve arquivos e volumes existentes.

Construa e inicie API e worker em containers separados:

```bash
docker compose up -d --build --wait
docker compose ps
curl --fail http://127.0.0.1:8000/health/ready
curl --fail http://127.0.0.1:9001/health/ready
```

Migrations devem ser executadas pelo serviço `setup`, não concorrentemente por
cada réplica. API e worker executam como UID `10001`; seus dados duráveis ficam
nos volumes de PostgreSQL, Azurite e RabbitMQ. Os diretórios e endpoints
publicados escutam em loopback por padrão. As URLs internas dos serviços são
`postgres:5432`, `rabbitmq:5672` e `http://azurite:10000/docpipe`.

Ao terminar, preserve os volumes:

```bash
docker compose stop
```

Para reiniciar os containers mantendo os dados, use `docker compose start`.
Para recriá-los preservando os volumes, execute `docker compose down --remove-orphans`
e repita os passos de setup e inicialização acima. Não use `down --volumes` no
ambiente de desenvolvimento: essa opção apaga os dados persistidos.

## API

| Método | Rota | Resultado |
| --- | --- | --- |
| `POST` | `/v1/documents` | `202` após arquivo, documento e outbox seguros |
| `GET` | `/v1/documents/{document_id}` | metadados privados ou `404` |
| `GET` | `/health/live` | vida do processo |
| `GET` | `/health/ready` | banco e storage aptos para ingestão |
| `GET` | `/metrics` | métricas da API em formato compatível com Prometheus |

As respostas e eventos nunca incluem binário, caminho físico, URL pública,
connection string ou credencial. O RabbitMQ não participa da readiness da API
porque a outbox preserva eventos aceitos. A readiness do worker exige conexão
com PostgreSQL e canal RabbitMQ utilizável para publicar.

O arquivo enviado tem limite padrão de 10 MiB
(`DOCPIPE_INGESTION_MAX_FILE_SIZE_BYTES`). O corpo total do `POST`, incluindo
o envelope multipart, pode usar até 64 KiB adicionais. Ambos os limites
produzem `413` quando excedidos; o limite do corpo é verificado durante a
leitura, inclusive sem `Content-Length` confiável.

## Instrumentação e telemetria

API e worker emitem logs JSON com `correlation_id`, `trace_id` e `span_id`.
O worker expõe métricas e saúde em `127.0.0.1:9001` por padrão. Por padrão,
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

O reenvio controlado de eventos esgotados preserva IDs e payload, e rejeita
eventos publicados ou não esgotados. Execute-o pela imagem de aplicação:

```bash
docker compose --profile setup run --rm --no-deps setup \
  python -m docpipe_ingestion.requeue_event EVENT_UUID
```

O comando de reconciliação é somente leitura e não apaga objetos:

```bash
docker compose --profile setup run --rm --no-deps setup \
  python -m docpipe_ingestion.reconcile_storage
```

Uploads incompletos só são listados após a idade configurada em
`DOCPIPE_INGESTION_INCOMPLETE_FILE_AGE_SECONDS` (uma hora por padrão). A
reconciliação identifica marcadores e blobs órfãos sem removê-los.

Se o worker perder o canal RabbitMQ, ele registra o erro e encerra sem marcar
eventos pendentes como publicados. Restaure o broker e inicie novamente o
worker; eventos esgotados ainda exigem reenvio controlado.

```bash
docker compose up -d rabbitmq
docker compose start worker
```

Este repositório mantém a instrumentação, sem hospedar uma stack central.
O Compose principal contém PostgreSQL, RabbitMQ, Azurite, API e worker. Logs
são emitidos em stderr, métricas são consultadas nos endpoints locais e traces podem ser
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

A Etapa 9 comprova por HTTP o blob, metadados, outbox, mensagem, falhas,
reenvio, reconciliação e persistência com os componentes reais do Compose.
Essas verificações funcionais não são ensaios experimentais de resiliência.
Para o notebook de 8 GB, o percurso usa uma API, um worker e verificações
sequenciais; uma VM pode hospedar o mesmo Compose sem caracterizar integração
Azure. A Etapa 10 revisa essas evidências para a candidata `v1.0.0`.

## Integração contínua

O workflow de CI valida pull requests destinadas à `main`, pushes na `main` e
execuções manuais. Os checks estáveis são `ci-quality`, `ci-tests` e
`ci-image`: eles cobrem qualidade, testes sem serviços, integrações reais com
PostgreSQL, RabbitMQ e Azurite, construção da imagem e prova funcional da
aplicação empacotada no Compose oficial. A imagem não é publicada e nenhum
deploy é realizado.

O teste `packaged` usa o checkout somente como harness de verificação. API,
worker e comandos operacionais são executados a partir da imagem construída,
sem mounts do checkout. O relatório JUnit exige o teste integrado e rejeita
ausência, vazio, falhas, erros ou skips.

Consulte `docs/CI.md` para os comandos equivalentes, isolamento dos serviços,
diagnóstico, checks obrigatórios da branch e limitações das
validações locais.

## Histórico experimental preservado

O laboratório implementado sob a antiga Etapa 9 permanece em `experiments/`,
nos Compose experimentais e no workflow manual. Seus comandos e limitações
estão preservados em [EXPERIMENTS.md](docs/EXPERIMENTS.md), sem constituir
roteiro obrigatório das novas etapas. Resultados ficam em
`artifacts/experiments/<run_id>/`, fora do Git.

A evidência local inspecionada registra uma tentativa de smoke bloqueada por
memória, sem requisições executadas. A existência dos scripts ou do workflow
não comprova ensaio concluído. Preservar outros relatórios e evidências
disponíveis sem atribuir resultados não verificados. Novos experimentos não
bloqueiam a `v1.0.0` e seu planejamento segue o marco Azure descrito acima.
