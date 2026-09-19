# Plano de implementação do DocPipe Ingestion

O plano é incremental. Cada etapa deve terminar com código executável, testes e documentação atualizada. O Codex deve implementar apenas a etapa solicitada.

As Etapas 1 a 7 estão concluídas e integradas à branch principal. As Etapas 8
a 10 completam a `v1.0.0`, uma entrega local reproduzível sem conta,
assinatura ou recursos de cloud provider. Implantação e integração com serviços
Azure pertencem ao roadmap da `v1.1.0`.

## Etapa 1 — Fundação do repositório

**Objetivo:** criar a base mínima e verificável do serviço.

- iniciar o projeto com `uv` e Python 3.13+;
- criar estrutura simples para API, domínio, aplicação, infraestrutura e testes;
- configurar FastAPI, Pydantic Settings e endpoint de liveness;
- configurar formatter, lint, verificação de tipos e pytest;
- incluir `.env.example`, `.gitignore` e Dockerfile inicial;
- documentar comandos locais no `README.md`.

**Saída verificável:** aplicação inicia, `/health/live` responde e pipeline local de qualidade passa.

**Estado:** concluída.

## Etapa 2 — Domínio e persistência de metadados

**Objetivo:** modelar o documento e seu ciclo inicial.

- implementar entidades, estados e schemas;
- configurar SQLAlchemy e SQLite;
- criar migration inicial para `documents` e `outbox_events`;
- implementar repositórios e testes de persistência;
- habilitar chaves estrangeiras e configurar timeout de bloqueio;
- validar o modo WAL no ambiente de teste;
- garantir horários UTC e UUIDs.

**Saída verificável:** migrations sobem em banco vazio e os testes gravam/consultam documentos e eventos outbox.

**Estado:** concluída.

## Etapa 3 — Validação e armazenamento local

**Objetivo:** receber arquivos com segurança e memória limitada.

- definir interface de armazenamento;
- implementar adaptador local com raiz em `dataset/documents/`;
- gerar nomes físicos opacos e impedir escape da raiz configurada;
- ignorar no Git os documentos e o arquivo SQLite gerados em execução;
- implementar validações de tipo, tamanho e assinatura;
- calcular SHA-256 durante streaming;
- criar caso de uso de ingestão;
- testar falhas e limites.

**Saída verificável:** arquivo válido é armazenado em `dataset/documents/` e
entradas inválidas são rejeitadas sem persistência incorreta.

**Estado:** concluída.

## Etapa 4 — API de documentos

**Objetivo:** disponibilizar o contrato HTTP versionado da `v1.0.0`.

- implementar `POST /v1/documents`;
- implementar `GET /v1/documents/{document_id}`;
- padronizar respostas e erros;
- criar testes de integração da API;
- documentar OpenAPI e exemplos.

**Saída verificável:** contratos de `docs/DESIGN.md` e critérios RF-001 a
RF-005/RF-007 passam nos testes.

**Estado:** concluída.

## Etapa 5 — Outbox e mensageria

**Objetivo:** publicar eventos sem perder o vínculo com a persistência.

- gravar documento e outbox na mesma transação;
- definir interface de broker e schema `document.received.v1`;
- implementar publicador com confirmação, retry e backoff;
- criar adaptador RabbitMQ para o laboratório local;
- testar indisponibilidade, duplicidade e reinício.

**Saída verificável:** falha do broker mantém o evento pendente e a recuperação publica sem perda.

**Estado:** concluída.

## Etapa 6 — Persistência compartilhada para escala

**Objetivo:** remover as limitações de instância única antes dos testes
distribuídos, sem depender de conta ou recursos Azure.

- executar PostgreSQL localmente por Docker Compose, mantendo a interface de
  persistência;
- executar Azurite localmente por Docker Compose como armazenamento de objetos
  compartilhado;
- implementar um adaptador compatível com a API do Azure Blob Storage e
  validá-lo contra o Azurite;
- criar container privado, volume persistente e health check para o Azurite;
- preservar a chave lógica, streaming, checksum e metadados do documento;
- manter SQLite e storage local disponíveis para testes rápidos;
- selecionar banco e storage por configuração;
- manter o RabbitMQ e o contrato `document.received.v1` sem alterações;
- adicionar testes de contrato compartilhados entre os adaptadores local e de
  objetos;
- testar PostgreSQL e Azurite sem exigir conta ou credenciais Azure.

**Saída verificável:** os adaptadores respeitam as mesmas interfaces e a
aplicação troca SQLite/storage local por PostgreSQL/Azurite via configuração.
Os contratos HTTP e de evento permanecem inalterados, e duas ou mais instâncias
da aplicação conseguem acessar o mesmo armazenamento de objetos no laboratório
local.

**Fora do escopo desta etapa:** Azure Blob Storage real, Azure Service Bus,
Managed Identity, RBAC e criação de qualquer recurso Azure. Uma validação no
Azure poderá ser planejada posteriormente sem alterar o domínio nem os
contratos públicos.

**Estado:** implementada localmente com PostgreSQL, Azurite, composição por
configuração, coordenação concorrente da outbox e suítes de integração opt-in.
O PostgreSQL do laboratório inicia vazio; dados SQLite não são migrados
automaticamente.

## Etapa 7 — Observabilidade

**Objetivo:** tornar o comportamento mensurável e correlacionável.

- incluir logs JSON e middleware de `correlation_id`;
- instrumentar métricas HTTP, storage, banco, outbox e broker;
- adicionar traces OpenTelemetry;
- implementar readiness e `/metrics`;
- criar dashboard mínimo e consultas de diagnóstico.

**Saída verificável:** uma ingestão pode ser acompanhada em logs, métricas e trace sem expor conteúdo.

**Estado:** implementada com logs JSON correlacionados, métricas separadas da
API e do worker, traces OTLP, contexto W3C privado na outbox, readiness de banco
e storage e stack opcional Prometheus/Grafana/Tempo.

## Etapa 8 — Containers e Kubernetes local com Kind

**Objetivo:** executar e escalar o laboratório oficial da `v1.0.0` em Kind,
sem dependência de registry externo ou recursos Azure.

- endurecer o Dockerfile com usuário não root e imagem enxuta;
- criar um cluster Kind single-node adequado ao notebook com 8 GB de RAM;
- fixar a versão do node image do Kind durante a implementação;
- construir localmente a imagem do DocPipe Ingestion e carregá-la com
  `kind load docker-image`;
- manter manifests Kubernetes como requisito; Helm ou Kustomize são opcionais,
  não obrigatórios;
- executar API e worker em Deployments separados;
- disponibilizar PostgreSQL, RabbitMQ e Azurite no laboratório por Services
  internos;
- configurar ConfigMaps, referências a Secrets locais sem valores reais
  versionados e PersistentVolumeClaims quando necessários;
- configurar liveness e readiness probes e requests/limits conservadores;
- executar migrations de forma controlada por Job;
- declarar a escalabilidade da API e testar uma e múltiplas réplicas;
- permitir acesso por `kubectl port-forward` ou mecanismo local equivalente;
- ativar a stack de observabilidade somente quando necessária;
- documentar comandos reproduzíveis para criar, validar e remover o cluster.

**Saída verificável:** o cluster Kind single-node pode ser recriado localmente,
recebe a imagem sem registry externo, executa API e worker saudáveis e permite
validar uma e múltiplas réplicas da API sobre PostgreSQL, Azurite e RabbitMQ.

**Fora do escopo:** AKS, Azure Container Registry, cloud load balancer, domínio
ou TLS públicos, quaisquer recursos Azure, múltiplos nós obrigatórios e
infraestrutura como código de cloud. Kind não deve ser apresentado como
equivalente ao AKS nem como ambiente de produção.

**Estado:** planejada para a `v1.0.0`.

## Etapa 9 — Testes locais de carga e resiliência no Kind

**Objetivo:** produzir no Kind evidências reproduzíveis da `v1.0.0` para o TCC.

- criar dataset sintético pequeno e reutilizável;
- implementar cenários Locust de upload e consulta;
- executar baseline com uma réplica da API;
- repetir com múltiplas réplicas e comparar throughput, sem definir metas ou
  thresholds antes do baseline;
- registrar p50, p95, p99, taxa de erro, CPU e memória;
- observar backlog, tentativas, publicação e recuperação da outbox;
- testar RabbitMQ indisponível e sua recuperação;
- testar separadamente reinício da API e reinício do worker;
- testar indisponibilidade temporária de PostgreSQL ou Azurite e recuperação;
- verificar a persistência dos dados durante os cenários de resiliência;
- coletar métricas Prometheus e traces OpenTelemetry;
- versionar scripts e documentar ambiente, dataset, parâmetros e resultados
  necessários à reprodução.

**Saída verificável:** experimentos locais no Kind podem ser repetidos e
comparam uma e múltiplas réplicas com os mesmos parâmetros, incluindo métricas,
traces e efeitos das falhas controladas sobre dados e outbox.

**Fora do escopo:** AKS e qualquer teste ou validação no Azure.

**Estado:** planejada para a `v1.0.0`.

## Etapa 10 — Fechamento e tag da `v1.0.0`

**Objetivo:** consolidar uma release local, segura, operacional e reproduzível.

- revisar todos os requisitos e cenários de aceite;
- executar todos os testes;
- revisar segurança, privacidade, limites, permissões, logs e tratamento de
  erros;
- revisar requests/limits e o consumo observado dos recursos;
- verificar imagens e dependências;
- confirmar a ausência de segredos reais no repositório e nas imagens;
- consolidar as evidências reproduzíveis do TCC;
- atualizar diagramas, contratos, procedimentos operacionais e de reprodução;
- documentar limitações do laboratório, do Kind e do Azurite;
- registrar o backlog da `v1.1.0` sem apresentá-lo como implementado;
- criar uma release candidate e preparar a tag `v1.0.0`.

**Saída verificável:** checklist de requisitos atendido, testes verdes,
documentação operacional e evidências consolidadas; o laboratório pode ser
reproduzido do zero sem conta Azure; a release candidate está pronta para a
tag `v1.0.0`.

**Estado:** planejada para a `v1.0.0`.

## Roadmap da `v1.1.0` — Azure

A `v1.1.0` fica reservada para implantação e integração com:

- Azure Kubernetes Service;
- Azure Container Registry;
- Azure Database for PostgreSQL Flexible Server;
- Azure Blob Storage real;
- Azure Key Vault;
- Managed Identity e RBAC;
- rede e endpoints privados;
- ingress, domínio e TLS no Azure;
- Azure Monitor ou Application Insights, se aprovados;
- infraestrutura como código;
- análise FinOps e custos Azure;
- políticas de backup, disponibilidade e recuperação;
- validação da aplicação no ambiente Azure.

A possível troca do RabbitMQ por Azure Service Bus será avaliada futuramente;
ela não está confirmada. Esse roadmap não integra a definição de pronto da
`v1.0.0`.

## Regras para avançar

- Não avance com teste falhando sem registrar e resolver a causa.
- Não pule para infraestrutura compartilhada antes de validar SQLite e
  `dataset/documents/` localmente.
- Não defina metas de desempenho antes do baseline.
- Registre decisões relevantes em `docs/DESIGN.md` ou em ADRs futuros.
- Uma PR deve representar preferencialmente uma tarefa pequena de uma única etapa.
