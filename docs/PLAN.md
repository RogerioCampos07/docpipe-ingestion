# Plano de implementação do DocPipe Ingestion

O plano é incremental. Cada etapa deve terminar com resultado verificável e
documentação atualizada. As Etapas 1 a 8 permanecem registradas como concluídas;
esse histórico não comprova o funcionamento da revisão atual. A Etapa 9 passa
a concluir a implementação funcional e a Etapa 10 valida o conjunto e encerra
a `v1.0.0`, sem uma etapa adicional de conclusão.

A entrega será local/portátil com Docker Compose, PostgreSQL como banco
exclusivo do Ingestion, Azurite para blobs privados e RabbitMQ para mensageria.
API e worker serão processos separados e não dependerão de Processing ou de
outros microsserviços. Azure pertence à `v1.1.0`. O planejamento de carga e
resiliência ocorrerá somente após a validação funcional no ambiente Azure com
Blob Storage e PostgreSQL.

Este replanejamento altera somente documentos. Não implementa tarefas nem
conclui as Etapas 9 e 10. Scripts, workflows e evidências do laboratório da
antiga Etapa 9 permanecem preservados em seu contexto histórico, descrito em
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
aceite integrado na Etapa 10; não exige refazer os adaptadores existentes.

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

`Settings` e `.env.example` ainda usam SQLite e storage local por padrão. O
Compose principal contém somente as três dependências; API e worker estão
no Compose experimental. A imagem ainda executa como root. O diagnóstico
existente é somente leitura e falta o reenvio controlado exigido pelo RNF-003.

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
5. **9.5 — Entregar testes e documentação correspondentes.** Cada tarefa
   anterior inclui testes das alterações. Fortalecer o caso de confirmação
   seguida de falha no commit, preservando a entrega pelo menos uma vez.
   Preparar validação funcional da aplicação empacotada independente do
   laboratório experimental. Atualizar instalação, configuração, operação,
   contratos e procedimentos de falha. Não adicionar deduplicação por checksum
   nem `Idempotency-Key`: uploads repetidos podem gerar documentos distintos,
   e republicações da outbox conservam o mesmo `event_id`.

**Arquivos previstos:** `docker-compose.yml`, `Dockerfile`, `.env.example`,
settings, composição, persistência, diagnóstico e casos de uso pertinentes;
testes correspondentes e documentação existente. `migrations/`,
`pyproject.toml` e `uv.lock` só mudam quando houver necessidade concreta.
Essas alterações de implementação ainda não foram executadas.

### Critérios de aceite da Etapa 9

- Compose principal contempla API, worker e PostgreSQL, Azurite e RabbitMQ;
- PostgreSQL é o único banco operacional, com migrations reproduzíveis em
  banco vazio e nenhuma transferência de dados presumida;
- aplicação executa sem root e preserva dados nos volumes apropriados;
- testes pertinentes de cada mudança e checks de qualidade passam, sem
  reduzir cobertura ou substituir validação PostgreSQL por SQLite;
- reenvio controlado, diagnóstico de órfãos e reinício do worker possuem
  procedimentos executáveis e testes pertinentes;
- contratos HTTP e de evento, transação documento/outbox, publisher confirms,
  privacidade e entrega pelo menos uma vez permanecem preservados;
- instruções de execução e validação estão coerentes com a implementação e
  prontas para a comprovação integrada da Etapa 10.

**Fora do escopo:** recursos funcionais adicionais, Azure, Kubernetes,
observabilidade central e ensaios experimentais de carga ou resiliência.

**Estado:** replanejada; implementação e aceite pendentes. Reaproveitar os
componentes corretos existentes. A atualização documental não conclui a etapa.

## Etapa 10 — Validação integrada e fechamento da `v1.0.0`

**Objetivo:** comprovar o serviço completo em ambiente local/portátil e
encerrar a `v1.0.0` nesta etapa, com requisitos atendidos, evidências
rastreáveis e documentação reproduzível.

### Tarefas em ordem de dependência

1. **10.1 — Reproduzir uma instalação limpa.** Após o aceite da Etapa 9,
   seguir somente as instruções do repositório em projeto Compose isolado.
   Registrar revisão, versões, configuração não sensível e ambiente. Construir
   a imagem, iniciar dependências, aplicar migrations em PostgreSQL vazio,
   preparar blobs e iniciar API e worker. Confirmar usuário não root e saúde.
2. **10.2 — Conferir o fluxo completo.** Usar HTTP real contra a API
   empacotada e worker em processo separado, com PostgreSQL, Azurite e RabbitMQ
   reais, sem mocks dessas integrações. Para PDF, PNG e JPEG sintéticos,
   conferir `202`, consulta por UUID, conteúdo e SHA-256 do blob privado,
   metadados, outbox, envelope e propriedades AMQP da mensagem e estado
   `PUBLISHED`. Verificar correlação e ausência de dados sensíveis. Demonstrar
   publicação sem Processing e sem consumidores de negócio; a leitura da fila
   pela verificação ocorre depois e não é processamento posterior.
3. **10.3 — Verificar erros, duplicidade e persistência.** Executar os casos
   funcionais de `REQUIREMENTS.md`, seção 4: rejeições sem sucesso parcial,
   indisponibilidade de banco/storage com erro controlado, broker indisponível
   com outbox preservada, retomada de pendentes e reenvio controlado de
   esgotados. Conferir órfãos sem apagá-los em falha incerta. Validar uploads
   repetidos e republicação segundo os contratos. Reiniciar API, worker e
   dependências e recriar containers preservando volumes, comprovando
   permanência de metadados, blobs, mensagens duráveis e eventos pendentes.
4. **10.4 — Validar a configuração adotada na CI.** Preservar `ci-quality`,
   `ci-tests` e `ci-image`. Ampliar a validação da imagem para API e worker com
   PostgreSQL, Azurite e RabbitMQ, mantendo qualidade, tipos, cobertura e
   integrações reais. Atualizar as exigências JUnit para impedir sucesso com
   testes obrigatórios ausentes ou ignorados. Preservar verificações dos
   scripts e variantes experimentais; não executar benchmarks no fluxo de PR.
5. **10.5 — Corrigir defeitos e consolidar evidências.** Corrigir problemas
   encontrados na execução futura desta etapa, adicionar regressões e repetir
   verificações afetadas. Executar os checks pertinentes existentes. Vincular
   RFs e RNFs obrigatórios aos resultados da revisão candidata e aos jobs do
   GitHub. Revisar segurança, privacidade, contratos, instalação, configuração,
   operação e limitações nos documentos existentes. Preservar relatórios
   sanitizados e referências duráveis às evidências, sem documentos recebidos,
   segredos ou dumps de dados no Git.
6. **10.6 — Fechar a versão.** Alinhar a versão do pacote, lockfile,
   metadados e documentação, preservando `/v1` e `document.received.v1`.
   Registrar revisão candidata, notas de release, evidências, limitações e a
   decisão de aceite. Conferir os critérios abaixo antes de declarar o
   fechamento técnico da `v1.0.0`; não transferir sua conclusão para outra
   etapa. Quando expressamente autorizados, integrar a revisão aprovada e
   criar a tag `v1.0.0` e a release vinculadas à revisão validada. Commit,
   push, PR, merge, tag e publicação exigem autorizações próprias; o plano
   não as concede. Registrar separadamente se esses atos formais estão
   pendentes, sem afirmar que a release foi publicada. Após os ajustes finais,
   confirmar que os checks e as evidências correspondem à revisão de fechamento.

As falhas e recuperações de 10.3 verificam contratos, integridade e retomada
previstos no RF-006 e RNF-003. Não são campanhas experimentais de injeção de
falhas, testes de carga nem avaliações de desempenho. Permanecem obrigatórias
mesmo com o adiamento dos experimentos.

### Critérios de aceite e fechamento

- instruções reproduzem instalação e inicialização a partir de banco vazio;
- API e worker empacotados funcionam com os três componentes reais do Compose,
  sem outro microsserviço, checkout ou consumidor de negócio;
- armazenamento privado, persistência transacional e publicação são
  conferidos conjuntamente, conforme os contratos;
- erros, duplicidade permitida, reenvio controlado e persistência após
  reinícios têm evidências, sem promessa de entrega exatamente uma vez;
- RFs e RNFs obrigatórios possuem testes e resultados rastreáveis;
- checks pertinentes passam, inclusive no GitHub para a revisão candidata;
- documentação, versão, segurança e limitações estão revisadas, sem segredos;
- não há requisito obrigatório pendente nem validação essencial omitida.

**Saída verificável:** `v1.0.0` tecnicamente concluída, autônoma, funcional e
validada em Docker Compose, com PostgreSQL próprio, Azurite e RabbitMQ. O
fechamento e seus atos formais ficam registrados nesta etapa; publicação
pendente de autorização não pode ser apresentada como realizada.

**Estado:** planejada; validação integrada e fechamento pendentes. Checks
antigos ou atualização documental não atendem aos critérios de aceite.

### Execução portátil e comandos de validação

Considerar o notebook de 8 GB: uma API, um worker e verificações sequenciais,
sem gerador de carga ou stack central. Conferir a memória realmente disponível
ao host e ao Docker. Uma VM pode hospedar o mesmo Compose se necessário; isso
não constitui integração com produtos Azure nem autoriza criar infraestrutura.

Os comandos existentes estão em `docs/CI.md`: instalação com
`uv sync --locked --group dev`, tarefas `lint`, `format-check`, `typecheck`,
`test`, `typos`, testes de integração opt-in, validação Compose e build.
Migrations usam `alembic upgrade head`; blobs usam
`python -m docpipe_ingestion.init_blob_storage`; diagnóstico usa
`python -m docpipe_ingestion.diagnostics CORRELATION_UUID`.

Na implementação, confirmar os comandos Compose de inicialização completa,
migrations, parada e reinício com volumes preservados. Criar ou completar o
comando de reenvio, o acesso operacional à reconciliação e a sequência de
validação funcional integrada. Não apresentar esses comandos futuros como
disponíveis hoje. Alguns testes atuais limpam tabelas e filas: executá-los
somente contra recursos descartáveis, separados das evidências preservadas.

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
