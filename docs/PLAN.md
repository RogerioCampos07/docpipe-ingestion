# Plano de implementação do DocPipe Ingestion

O plano é incremental. Cada etapa deve terminar com resultado verificável e
documentação atualizada. As Etapas 1 a 8 permanecem registradas como concluídas;
esse histórico não comprova o funcionamento da revisão atual. A Etapa 9
conclui a operação local, suas provas funcionais integradas e a adequação do
`ci-image`. A Etapa 10 revisa as evidências, verifica a versão candidata e
prepara o aceite local da `v1.0.0`.

A entrega será local/portátil com Docker Compose, PostgreSQL como banco
exclusivo do Ingestion, Azurite para blobs privados e RabbitMQ para mensageria.
API e worker serão processos separados e não dependerão de Processing ou de
outros microsserviços. Azure pertence à `v1.1.0`. O aceite funcional local e
o planejamento experimental após validação funcional Azure são marcos
distintos; os experimentos não bloqueiam o fechamento local da `v1.0.0`.

O replanejamento realocou as provas integradas e a adaptação de CI para a
Etapa 9. A Etapa 10 fica dedicada à revisão das evidências e à preparação da
candidata local. Scripts, workflows e evidências do laboratório da antiga
Etapa 9 permanecem preservados em seu contexto histórico, descrito em
`docs/EXPERIMENTS.md`.

## Diretriz obrigatória em todas as etapas

Todos os microsserviços atuais e futuros do DocPipe devem ser desacoplados,
independentes e possuir utilidade própria. Toda implementação e revisão deve
preservar as fronteiras de `DESIGN.md`, seção 19, e os critérios do RNF-009 de
`REQUIREMENTS.md`, incluindo recursos próprios e contratos compatíveis.

A auditoria anterior, por inspeção estática, concluiu que o Ingestion atende
à diretriz e não precisa de refatoração. Não houve validação operacional
naquela auditoria. Este registro não cria uma etapa de refatoração, não
reclassifica etapas concluídas nem autoriza avançar as etapas pendentes.

## Etapa 1 — Fundação do repositório

**Objetivo:** criar a base mínima e verificável do serviço.

- iniciar o projeto com `uv` e Python 3.13+;
- criar a estrutura da aplicação e dos testes;
- configurar FastAPI, settings, liveness, qualidade e Dockerfile;
- documentar os comandos locais.

**Estado:** concluída.

## Etapa 2 — Domínio e persistência de metadados

**Objetivo:** modelar o documento, SQLite, migrations e outbox.

**Estado:** concluída.

## Etapa 3 — Validação e armazenamento local

**Objetivo:** receber arquivos por streaming, validá-los e armazená-los com
chaves opacas em `dataset/documents/`.

**Estado:** concluída.

## Etapa 4 — API de documentos

**Objetivo:** implementar os contratos HTTP versionados de criação e consulta.

**Estado:** concluída.

## Etapa 5 — Outbox e mensageria

**Objetivo:** registrar documento e evento na mesma transação e publicar
`document.received.v1` no RabbitMQ com confirmação, retry e backoff.

**Estado:** concluída.

## Etapa 6 — Persistência compartilhada para escala

**Objetivo:** permitir o laboratório compartilhado com PostgreSQL e Azurite,
preservando SQLite e storage local no modo simples.

**Saída verificada:** adaptadores selecionáveis por configuração, contratos
preservados, coordenação concorrente da outbox e testes de integração opt-in.
O PostgreSQL do laboratório inicia vazio; dados SQLite não são migrados
automaticamente.

**Estado:** concluída.

Esse registro descreve a entrega da Etapa 6. A decisão posterior para a
`v1.0.0` é adotar PostgreSQL como único banco operacional na Etapa 9, com
provas integradas nesta etapa; não exige refazer os adaptadores existentes.

## Etapa 7 — Instrumentação do serviço

**Objetivo:** emitir sinais que tornem a API e o worker mensuráveis e
correlacionáveis, sem acoplá-los a um backend de observabilidade.

- emitir logs JSON estruturados;
- gerar e propagar `correlation_id`;
- incluir `trace_id` e `span_id` quando aplicável;
- expor métricas da aplicação;
- instrumentar traces e propagar W3C Trace Context;
- manter liveness e readiness;
- configurar a instrumentação por variáveis de ambiente;
- exportar telemetria para endpoints configuráveis;
- testar sinais, propagação e ausência de dados sensíveis;
- documentar os sinais emitidos pelo serviço.

**Saída verificada:** uma ingestão pode ser acompanhada pelos sinais emitidos
pela API e pelo worker; o contrato do evento permanece inalterado; exporters
não participam da readiness da API; a instrumentação não exige um backend
específico.

**Estado:** concluída.

OpenTelemetry Collector, Prometheus, Grafana, Jaeger, Tempo, Loki, dashboards,
alertas, armazenamento e configuração central de observabilidade não pertencem
à responsabilidade deste repositório. O Compose, as configurações e o
dashboard centrais de Prometheus, Grafana e Tempo foram removidos em uma
refatoração preparatória à Etapa 8, sem criar uma nova etapa numerada nem
reverter a instrumentação da Etapa 7. A referência histórica está em
`docs/OBSERVABILITY.md`.

## Etapa 8 — CI com GitHub Actions

**Objetivo:** validar mudanças de forma reproduzível em pull requests e pushes
para `main`, sem realizar entrega ou implantação contínua.

- criar workflows na pasta `.github/`, preservando o `CODEOWNERS` existente;
- instalar dependências de forma reproduzível com `uv` e o lockfile;
- executar Ruff, typos e pytest;
- executar os testes unitários, de contrato e de integração existentes;
- iniciar PostgreSQL, RabbitMQ e Azurite somente para testes que dependam deles;
- construir e validar a imagem Docker;
- aplicar permissões mínimas ao `GITHUB_TOKEN`;
- usar cache seguro baseado no lockfile;
- cancelar execuções obsoletas da mesma pull request;
- configurar timeouts;
- documentar os checks usados na proteção da `main`.

**Saída verificável:** pull requests e pushes para `main` executam os checks
documentados em ambiente limpo, e a imagem é construída e validada sem ser
publicada.

**Fora do escopo:** Kind, cluster Kubernetes, deploy automático, publicação
automática de imagens, Azure ou outro cloud provider, Locust em pull requests,
testes de carga no workflow padrão e stack central de observabilidade.

CI valida mudanças. CD permanece evolução futura para releases, publicação de
artefatos e implantação em ambientes aprovados; a `v1.0.0` não promete entrega
nem deploy contínuo.

**Estado:** concluída e mergeada. Os checks obrigatórios são `ci-quality`,
`ci-tests` e `ci-image`.

## Etapa 9 — Conclusão da implementação funcional da `v1.0.0`

**Objetivo:** completar as lacunas reais do escopo acordado e consolidar API,
worker, PostgreSQL próprio, Azurite e RabbitMQ no Docker Compose principal,
preservando a autonomia do Ingestion e os contratos existentes.

### Ponto de partida inspecionado

O suporte PostgreSQL já aparece em `pyproject.toml` (`psycopg[binary]`),
`src/docpipe_ingestion/infrastructure/database/engine.py`, `migrations/env.py`,
`tests/integration/test_postgresql.py` e `docker-compose.yml`. As migrations
existentes chegam a `20260918_03`. Isso comprova implementação disponível,
não aprovação operacional atual. Não há motivo identificado para recriar esse
suporte nem para adicionar outro driver.

O estado funcional precisa ser comprovado por execução. As alterações da
Etapa 9 devem configurar PostgreSQL e Azurite explicitamente, incluir API,
worker e preparação controlada no Compose principal, usar imagem não-root,
fornecer reenvio e preservar a reconciliação somente leitura. A presença das
alterações no código não substitui as validações abaixo.

### Tarefas em ordem de dependência

1. **9.1 — Aplicar a configuração operacional aprovada.** Tornar PostgreSQL
   o único banco suportado para execução da versão e Azurite o storage do
   percurso de entrega. Ajustar defaults, validações e exemplos, sem fallback
   silencioso para SQLite. SQLite pode permanecer apenas como recurso interno
   das fixtures existentes, selecionado explicitamente, sem representar um
   segundo banco operacional. Preservar o adaptador local e seus testes sem
   criar outro percurso obrigatório de release.
2. **9.2 — Consolidar persistência e migrations PostgreSQL.** Reutilizar
   SQLAlchemy, Alembic, driver e revisões existentes. Validar banco vazio,
   correspondência entre schema e modelos, constraints, horários UTC,
   transação conjunta de documento/outbox e `SKIP LOCKED`. Fortalecer o teste
   de rollback para incluir ambos os registros. Criar nova migration somente
   se uma correção exigir mudança de schema; verificar reversibilidade quando
   segura em banco descartável. Migração do schema não significa transferência
   de dados SQLite: não há transferência prevista nem exclusão de dados
   existentes. Dependências novas exigem necessidade concreta e uso de `uv`.
3. **9.3 — Completar o Compose principal e a imagem.** Incluir API e worker
   separados usando a imagem do serviço, endereços internos, saúde e ordem de
   inicialização adequados. Documentar a aplicação única e controlada das
   migrations e a preparação do container privado de blobs. Preservar volumes
   de PostgreSQL, Azurite e RabbitMQ. Executar a aplicação sem root, com
   permissões para os arquivos temporários necessários. A API não deve depender
   da presença de consumidores nem da disponibilidade do broker para aceitar
   documentos com segurança pela outbox.
4. **9.4 — Atender os procedimentos funcionais do RNF-003.** Disponibilizar
   comando operacional mínimo para reenviar eventos não publicados, inclusive
   esgotados, preservando `event_id`, `document_id`, correlação e payload.
   Impedir alteração de eventos já publicados e registrar a ação sem dados
   sensíveis. Documentar e tornar executável a identificação de órfãos e
   uploads incompletos pela reconciliação existente, sem exclusão automática.
   Documentar a restauração das dependências e o reinício explícito do worker
   quando perder o canal RabbitMQ; reconexão automática não é requisito novo.
   Reiniciar o worker não substitui o reenvio de eventos esgotados.
5. **9.5 — Completar as provas funcionais integradas.** Em projeto Compose
   isolado, usar a imagem construída, HTTP real e PostgreSQL, Azurite e
   RabbitMQ reais. Conferir PDF, PNG e JPEG, conteúdo privado e SHA-256,
   metadados, outbox, envelope e propriedades da mensagem, estado `PUBLISHED`,
   duplicatas permitidas, falha parcial, reenvio, retomada, reconciliação e
   persistência após reiniciar/recriar containers com volumes preservados.
   Não montar o checkout na API, no worker ou nos comandos operacionais da
   imagem. Os cenários de falha são funcionais e não campanhas experimentais.
6. **9.6 — Adaptar o check `ci-image`.** Preservar os checks
   `ci-quality`, `ci-tests` e `ci-image`, seus nomes, limites e proteções.
   Exercitar a imagem construída no Compose oficial com configuração explícita,
   migrations, preparação do Azurite, API, worker e HTTP. O harness pode usar
   bibliotecas do checkout para verificar os serviços, mas todos os processos
   da aplicação devem vir da imagem, sem mounts do checkout. Reutilizar o
   verificador JUnit para rejeitar relatórios ausentes/vazios, erros, falhas,
   skips e módulos obrigatórios ausentes; coletar diagnósticos e limpar somente
   recursos descartáveis do próprio projeto.
7. **9.7 — Alinhar a documentação.** Atualizar comandos reais de configuração,
   inicialização, validação, diagnóstico e encerramento. Registrar garantias e
   limites da arquitetura, autonomia do Ingestion, v1.0.0 local, Azure na
   v1.1.0 e marco experimental posterior. Não adicionar deduplicação por
   checksum nem `Idempotency-Key`: uploads repetidos podem gerar documentos
   distintos e republicações conservam o mesmo `event_id`.

**Arquivos previstos:** `docker-compose.yml`, `Dockerfile`, `.env.example`,
settings, composição, persistência, worker, comandos operacionais, testes,
`.github/workflows/ci.yml`, documentação existente e este `AGENTS.md`.
`migrations/`, `pyproject.toml` e `uv.lock` só mudam quando houver necessidade
concreta.

### Critérios de aceite da Etapa 9

- Compose principal contempla API, worker e PostgreSQL, Azurite e RabbitMQ;
- PostgreSQL é o único banco operacional, com migrations reproduzíveis em
  banco vazio e nenhuma transferência de dados presumida;
- aplicação executa sem root e preserva dados nos volumes apropriados;
- prova funcional integrada usa HTTP contra a imagem construída, com as três
  dependências reais, e confere blob privado, metadados, outbox, publicação,
  falhas, retomada, reenvio, reconciliação e persistência;
- `ci-image` exercita a imagem entregue sem substituir seus arquivos por
  mounts do checkout e mantém as proteções JUnit e os três checks existentes;
- testes pertinentes de cada mudança e checks de qualidade passam, sem
  reduzir cobertura ou substituir validação PostgreSQL por SQLite;
- reenvio controlado, diagnóstico de órfãos e reinício do worker possuem
  procedimentos executáveis e testes pertinentes;
- contratos HTTP e de evento, transação documento/outbox, publisher confirms,
  privacidade e entrega pelo menos uma vez permanecem preservados;
- instruções de execução e validação estão coerentes com a implementação e
  reproduzem o ambiente local de ponta a ponta;
- a Etapa 10 revisa evidências rastreáveis da candidata, sem exigir Azure ou
  novos experimentos para o aceite local da `v1.0.0`.

**Fora do escopo:** recursos funcionais adicionais, Azure, Kubernetes,
observabilidade central e ensaios experimentais de carga ou resiliência.

**Estado:** implementação em andamento; aceite pendente até todas as
validações integradas e os checks exigidos passarem. Reaproveitar os
componentes corretos existentes; código e documentação sem execução não
concluem a etapa.

## Etapa 10 — Revisão da candidata local `v1.0.0`

**Objetivo:** revisar as evidências funcionais da Etapa 9, verificar a versão
candidata e concluir sua preparação e aceite local como `v1.0.0`, com
requisitos atendidos, resultados rastreáveis e documentação reproduzível.

### Tarefas em ordem de dependência

1. **10.1 — Revisar evidências da Etapa 9.** Conferir revisão, versões,
   configuração não sensível, ambiente, comandos e resultados. Rastrear cada
   RF/RNF obrigatório aos testes, relatórios e diagnósticos sanitizados;
   investigar lacunas antes de aceitar a candidata.
2. **10.2 — Verificar a versão candidata.** Alinhar versão do pacote,
   lockfile, metadados e documentação, preservando `/v1` e
   `document.received.v1`. Reexecutar as verificações necessárias para
   confirmar que os resultados pertencem ao estado candidato e verificar os
   três checks no GitHub Actions quando a revisão passar pelo fluxo manual.
3. **10.3 — Corrigir defeitos da candidata e fechar evidências.** Corrigir
   problemas comprovados com regressões e repetir as verificações afetadas.
   Revisar segurança, privacidade, contratos, instalação, configuração,
   operação e limitações. Preservar relatórios sanitizados e referências
   duráveis antes de expirarem artefatos; não versionar documentos, segredos
   ou dumps.
4. **10.4 — Registrar a preparação local da `v1.0.0`.** Registrar revisão
   candidata, notas de versão, evidências, limitações e decisão de aceite.
   Distinguir o fechamento local de integração/publicação formal, que seguem
   as autorizações e o fluxo manual aplicáveis. Azure e experimentos futuros
   não são pré-requisitos desse aceite.

As falhas e recuperações funcionais são executadas na Etapa 9, conforme RF-006
e RNF-003. A Etapa 10 revisa se as evidências correspondem à candidata. Esses
testes não são campanhas experimentais de injeção de falhas, carga ou
desempenho.

### Critérios de aceite e fechamento

- evidências da Etapa 9 correspondem ao estado candidato e são reproduzíveis;
- RFs e RNFs obrigatórios estão rastreados a resultados reais;
- checks pertinentes passam, inclusive no GitHub para a revisão candidata;
- documentação, versão, segurança e limitações estão revisadas, sem segredos;
- o aceite local da `v1.0.0` não depende de Azure nem de experimentos
  acadêmicos posteriores;
- não há requisito obrigatório pendente nem validação essencial omitida.

**Saída verificável:** candidata `v1.0.0` revisada e preparada para aceite
local, com evidências rastreáveis da validação funcional em Docker Compose.
Integração e publicação formais não podem ser apresentadas como realizadas
enquanto estiverem pendentes.

**Estado:** planejada; revisão da candidata e preparação do aceite pendentes.
Checks antigos ou atualização documental não atendem aos critérios.

### Execução portátil e comandos de validação

Considerar o notebook de 8 GB: uma API, um worker e verificações sequenciais,
sem gerador de carga ou stack central. Conferir a memória realmente disponível
ao host e ao Docker. Uma VM pode hospedar o mesmo Compose se necessário; isso
não constitui integração com produtos Azure nem autoriza criar infraestrutura.

Os comandos existentes estão em `README.md` e `docs/CI.md`: instalação com
`uv sync --locked --group dev`, tarefas `lint`, `format-check`, `typecheck`,
`test`, `typos`, testes de integração opt-in, validação Compose e build.
Migrations e preparo de blobs usam o serviço Compose `setup`; comandos de
reenvio e reconciliação também executam nessa imagem. Diagnóstico por
correlação usa `python -m docpipe_ingestion.diagnostics CORRELATION_UUID`.

Os comandos Compose de inicialização, migrations, parada e reinício com
volumes preservados, junto ao reenvio e à reconciliação, pertencem à Etapa 9 e
devem ser documentados e testados antes do aceite. Alguns testes limpam tabelas
e filas: executá-los somente contra recursos descartáveis, separados das
evidências preservadas.

## Autonomia e composição futura do DocPipe

A autonomia é uma determinação atual, aplicável também aos serviços futuros,
conforme RNF-009. Cada serviço deve manter ainda imagem, health checks, logs
estruturados, correlation ID, métricas, instrumentação de traces e
configuração própria para exportar telemetria.

Um futuro repositório integrador ou de plataforma poderá concentrar a
composição dos microsserviços, a configuração integrada, a stack central de
observabilidade, dashboards, alertas, testes ponta a ponta, testes integrados
de carga e resiliência, eventual topologia Kubernetes e infraestrutura
compartilhada. A separação de responsabilidades está aprovada; o repositório
ainda não existe, e sua implementação e arquitetura não estão definidas. Kind
poderá ser avaliado nesse contexto de integração local, sem compromisso atual.

## Roadmap da `v1.1.0` — Azure

A `v1.1.0` entregará suporte aos produtos e serviços Azure, incluindo Blob
Storage e PostgreSQL, preservando a compatibilidade dos contratos públicos.
Sua implementação e validação serão planejadas posteriormente, sem implantação
cloud nas Etapas 9 e 10.

A possível adoção do Azure Service Bus continua sendo uma decisão futura, não
uma escolha confirmada. Esse roadmap não integra a definição de pronto da
`v1.0.0`.

O planejamento de novos ensaios de carga e resiliência ocorrerá somente após
o Ingestion estar funcional e validado nesse ambiente Azure com Blob Storage
e PostgreSQL. Não se definem aqui cenários, volumes, concorrência, ferramentas
ou metas de desempenho. O laboratório histórico não bloqueia a `v1.0.0`;
scripts, workflows, relatórios e evidências existentes devem ser preservados.

## Regras para avançar

- não avance com teste falhando sem registrar e resolver a causa;
- não substitua validações funcionais obrigatórias pelo adiamento experimental;
- preserve dados, volumes e evidências existentes;
- não declare concluída uma etapa com critérios obrigatórios pendentes;
- registre decisões relevantes no `docs/DESIGN.md` ou em ADRs futuros;
- mantenha cada mudança restrita à etapa solicitada.
