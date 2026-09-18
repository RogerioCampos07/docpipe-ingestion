# Plano de implementação do DocPipe Ingestion

O plano é incremental. Cada etapa deve terminar com código executável, testes e documentação atualizada. O Codex deve implementar apenas a etapa solicitada.

## Etapa 1 — Fundação do repositório

**Objetivo:** criar a base mínima e verificável do serviço.

- iniciar o projeto com `uv` e Python 3.13+;
- criar estrutura simples para API, domínio, aplicação, infraestrutura e testes;
- configurar FastAPI, Pydantic Settings e endpoint de liveness;
- configurar formatter, lint, verificação de tipos e pytest;
- incluir `.env.example`, `.gitignore` e Dockerfile inicial;
- documentar comandos locais no `README.md`.

**Saída verificável:** aplicação inicia, `/health/live` responde e pipeline local de qualidade passa.

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

## Etapa 4 — API de documentos

**Objetivo:** disponibilizar o contrato HTTP da primeira versão.

- implementar `POST /v1/documents`;
- implementar `GET /v1/documents/{document_id}`;
- padronizar respostas e erros;
- criar testes de integração da API;
- documentar OpenAPI e exemplos.

**Saída verificável:** contratos de `docs/DESIGN.md` e critérios RF-001 a
RF-005/RF-007 passam nos testes.

## Etapa 5 — Outbox e mensageria

**Objetivo:** publicar eventos sem perder o vínculo com a persistência.

- gravar documento e outbox na mesma transação;
- definir interface de broker e schema `document.received.v1`;
- implementar publicador com confirmação, retry e backoff;
- criar adaptador RabbitMQ para o laboratório local;
- testar indisponibilidade, duplicidade e reinício.

**Saída verificável:** falha do broker mantém o evento pendente e a recuperação publica sem perda.

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

## Etapa 8 — Container e Kubernetes

**Objetivo:** executar e escalar o serviço no laboratório.

- endurecer Dockerfile com usuário não root e imagem enxuta;
- criar manifests ou Helm chart para API e publicador;
- configurar recursos, probes, ConfigMap e referências a Secrets;
- preparar autoscaling da API;
- definir execução controlada das migrations.

**Saída verificável:** implantação em Kubernetes fica saudável e suporta
múltiplas réplicas usando os adaptadores compartilhados da Etapa 6.

## Etapa 9 — Testes de carga e resiliência

**Objetivo:** produzir evidências reproduzíveis para o TCC.

- criar dataset sintético pequeno reutilizável;
- implementar cenários Locust de upload e consulta;
- executar baseline local com uma réplica, SQLite e storage local;
- executar novo baseline com PostgreSQL e armazenamento de objetos;
- repetir com escalabilidade horizontal;
- testar broker indisponível e recuperação da outbox;
- registrar CPU, memória, throughput, erro e p50/p95/p99.

**Saída verificável:** scripts, parâmetros, ambiente e resultados permitem repetir e comparar os experimentos.

## Etapa 10 — Segurança e fechamento da versão

**Objetivo:** consolidar a primeira entrega demonstrável.

- revisar limites, permissões, logs e tratamento de erros;
- executar análise de dependências e imagem;
- verificar requisitos e cenários CT-001 a CT-010;
- atualizar diagramas, contratos e instruções de operação;
- registrar limitações e backlog da próxima versão;
- criar release candidata.

**Saída verificável:** checklist de requisitos atendido, testes verdes e documentação suficiente para demonstração e avaliação acadêmica.

## Regras para avançar

- Não avance com teste falhando sem registrar e resolver a causa.
- Não pule para infraestrutura compartilhada antes de validar SQLite e
  `dataset/documents/` localmente.
- Não defina metas de desempenho antes do baseline.
- Registre decisões relevantes em `docs/DESIGN.md` ou em ADRs futuros.
- Uma PR deve representar preferencialmente uma tarefa pequena de uma única etapa.
