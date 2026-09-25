# Plano de implementação do DocPipe Ingestion

O plano é incremental. Cada etapa deve terminar com resultado verificável e
documentação atualizada. As Etapas 1 a 6 estão concluídas. A Etapa 7 também
está concluída, com escopo redefinido para a instrumentação do serviço. As
antigas Etapas 8 e 9 foram descartadas; as novas Etapas 8 a 10 completam a
`v1.0.0` local e reproduzível.

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

## Etapa 9 — Carga, escalabilidade e resiliência local

**Objetivo:** produzir evidências acadêmicas reproduzíveis do serviço em
ambiente local, usando Docker Compose como ambiente principal e sem exigir
Kubernetes.

- criar massa de dados sintética e cenários Locust graduais;
- estabelecer baseline com uma API e um worker;
- comparar de forma controlada múltiplas instâncias quando tecnicamente
  aplicável, tratando ganho de desempenho como hipótese experimental;
- executar individualmente os cenários de resiliência;
- acompanhar transactional outbox, RabbitMQ e processamento assíncrono;
- coletar os logs, métricas e traces necessários às evidências;
- registrar throughput, p50, p95, p99, taxa de erro, CPU, memória e swap;
- testar reinícios e indisponibilidades temporárias com recuperação controlada;
- documentar ambiente, parâmetros, massa, resultados e limitações do notebook;
- permitir interrupção segura sem excluir volumes ou dados de forma
  indiscriminada.

**Saída verificável:** experimentos isolados e reproduzíveis com parâmetros e
evidências documentados, incluindo comportamento da outbox e recuperação após
falhas. A comparação de instâncias registra o resultado observado sem prometer
melhora prévia.

**Fora do escopo:** Kubernetes obrigatório, cloud provider e incorporação de
uma stack central de observabilidade. Um backend ou visualização central que
seja necessário a experimentos integrados pertence ao possível repositório
integrador futuro.

**Estado:** laboratório implementado nesta branch. A execução e revisão das
evidências locais ainda são necessárias para concluir a etapa; consulte
`docs/EXPERIMENTS.md`.

## Etapa 10 — Consolidação da `v1.0.0`

**Objetivo:** consolidar uma release local, segura e reproduzível.

- revisar requisitos, segurança, privacidade e tratamento de erros;
- revisar a instrumentação e os checks de CI;
- executar e consolidar os testes e as evidências acadêmicas;
- documentar limitações e o procedimento completo de execução local;
- verificar imagens, dependências e ausência de segredos reais;
- preparar a release e, posteriormente, criar a tag `v1.0.0`.

**Saída verificável:** requisitos revisados, checks verdes, evidências
consolidadas, limitações explícitas e procedimento local reproduzível. A
release fica pronta para a criação posterior da tag.

**Estado:** planejada para a `v1.0.0`.

## Arquitetura futura do DocPipe

Os microsserviços serão mantidos em repositórios separados. Cada repositório
deverá possuir código, testes, CI, imagem, health checks, logs estruturados,
correlation ID, métricas, instrumentação de traces e configuração própria para
exportar telemetria.

Um futuro repositório integrador ou de plataforma poderá concentrar a
composição dos microsserviços, a configuração integrada, a stack central de
observabilidade, dashboards, alertas, testes ponta a ponta, testes integrados
de carga e resiliência, eventual topologia Kubernetes e infraestrutura
compartilhada. A separação de responsabilidades está aprovada; o repositório
ainda não existe, e sua implementação e arquitetura não estão definidas. Kind
poderá ser avaliado nesse contexto de integração local, sem compromisso atual.

## Roadmap da `v1.1.0` — Azure

A `v1.1.0` reserva para avaliação e implementação futura:

- Azure Kubernetes Service;
- Azure Container Registry;
- Azure Database for PostgreSQL;
- Azure Blob Storage real;
- Azure Key Vault;
- Managed Identity e RBAC;
- rede, ingress e TLS no Azure;
- observabilidade gerenciada;
- infraestrutura como código;
- análise FinOps.

A possível adoção do Azure Service Bus continua sendo uma decisão futura, não
uma escolha confirmada. Esse roadmap não integra a definição de pronto da
`v1.0.0`.

## Regras para avançar

- não avance com teste falhando sem registrar e resolver a causa;
- não defina metas de desempenho antes do baseline;
- execute os cenários de resiliência separadamente;
- preserve dados e volumes ao interromper experimentos;
- registre decisões relevantes no `docs/DESIGN.md` ou em ADRs futuros;
- mantenha cada mudança restrita à etapa solicitada.
