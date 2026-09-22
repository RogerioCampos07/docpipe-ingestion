# Requisitos do DocPipe Ingestion

## 1. Requisitos funcionais

### RF-001 — Receber documento

O serviço deve receber um arquivo por requisição HTTP e devolver um identificador único.

**Critérios de aceite**

- aceita PDF, PNG e JPEG válidos;
- responde `202 Accepted` quando a ingestão é registrada com segurança;
- a resposta contém `document_id`, `status`, `correlation_id` e `received_at`;
- o identificador é UUID e não revela informação interna.

### RF-002 — Validar entrada

O serviço deve validar o documento antes de aceitá-lo.

**Critérios de aceite**

- rejeita arquivo vazio;
- rejeita tipo não permitido com `415`;
- rejeita arquivo acima do limite configurado com `413`;
- não confia apenas em extensão ou `Content-Type`;
- nomes e metadados inválidos não formam caminhos de armazenamento.

### RF-003 — Armazenar original

O serviço deve preservar o arquivo original em storage local ou no container
privado do Azurite, conforme configuração.

**Critérios de aceite**

- o nome físico é criado pelo sistema e não usa diretamente o nome original;
- a gravação é realizada por streaming;
- no backend local, o caminho resolvido permanece em `dataset/documents/`;
- no Azurite, a chave lógica é usada em container sem acesso público;
- o diretório não é exposto como conteúdo estático pela API;
- falha de armazenamento não produz uma resposta de sucesso.

### RF-004 — Registrar metadados

O serviço deve registrar os metadados necessários em SQLite ou PostgreSQL,
conforme configuração.

**Critérios de aceite**

- registra UUID, nome sanitizado, tipo, tamanho, SHA-256, chave do objeto, estado e horários UTC;
- o schema é criado por migrations compatíveis com SQLite e PostgreSQL;
- o conteúdo binário não é salvo no banco relacional.

### RF-005 — Calcular integridade

O serviço deve calcular o SHA-256 durante o recebimento do arquivo.

**Critérios de aceite**

- o checksum corresponde exatamente ao conteúdo armazenado;
- o cálculo não exige carregar o arquivo inteiro em memória;
- o valor aparece nos metadados e no evento.

### RF-006 — Publicar evento

O serviço deve produzir `document.received.v1` após a persistência do documento.

**Critérios de aceite**

- o evento segue o contrato de `docs/DESIGN.md`;
- banco e criação do evento outbox participam da mesma transação;
- o publicador confirma a entrega antes de marcar o evento como publicado;
- falhas temporárias utilizam retry com backoff;
- a solução assume entrega pelo menos uma vez.

### RF-007 — Consultar estado

O serviço deve permitir consulta dos metadados e do estado pelo UUID.

**Critérios de aceite**

- documento existente retorna `200`;
- documento ausente retorna `404`;
- a resposta não contém o binário nem credenciais de storage.

### RF-008 — Expor saúde e métricas

O serviço deve disponibilizar endpoints de liveness, readiness e métricas.

**Critérios de aceite**

- liveness não falha somente porque uma dependência externa está indisponível;
- readiness falha quando não é seguro aceitar novos documentos;
- métricas são expostas em formato compatível com coleta e sem dependência de
  backend específico;
- nenhum endpoint expõe segredo ou conteúdo de documento.

## 2. Requisitos não funcionais

### RNF-001 — Desempenho

- O upload deve utilizar streaming e memória limitada por requisição.
- A API não deve aguardar OCR ou processamento posterior.
- O experimento de carga deve medir percentis p50, p95 e p99, throughput e taxa de erro.
- Metas numéricas finais serão definidas após um teste de baseline documentado; não devem ser inventadas previamente.

### RNF-002 — Escalabilidade

- O modo simples da `v1.0.0` deve operar corretamente em uma única instância.
- O domínio não deve depender diretamente de SQLite nem do sistema de arquivos.
- O laboratório local da `v1.0.0` usa Docker Compose como ambiente principal.
- A comparação entre uma e múltiplas instâncias deve ocorrer somente quando
  tecnicamente aplicável, sem pressupor ganho antes do baseline.

### RNF-003 — Confiabilidade

- Falhas do broker não podem apagar documentos já aceitos.
- Operações externas devem possuir timeout.
- O publicador deve sobreviver a reinicializações sem perder eventos pendentes.
- Deve existir caminho controlado para identificar e reenviar eventos não publicados.

### RNF-004 — Segurança e LGPD

- Todo tráfego de produção deve usar TLS.
- Segredos devem vir de configuração protegida da plataforma.
- Logs não podem incluir conteúdo de arquivo nem dado pessoal desnecessário.
- O acesso ao diretório e ao arquivo SQLite deve seguir menor privilégio.
- O projeto deve documentar retenção, exclusão e rastreabilidade antes de uso com dados pessoais reais.
- Testes e demonstrações devem usar dados sintéticos ou anonimizados.

### RNF-005 — Observabilidade

- Todas as requisições devem possuir `correlation_id`.
- Logs, métricas e traces devem permitir seguir uma ingestão sem registrar o conteúdo.
- Métricas devem evitar labels de alta cardinalidade.
- Falhas em banco, storage e broker devem ser distinguíveis.
- A instrumentação deve exportar telemetria para endpoints configuráveis e
  permanecer desacoplada de coleta, armazenamento e visualização centrais.

### RNF-006 — Portabilidade

- O domínio e os casos de uso não devem depender diretamente de SQLite, do
  sistema de arquivos, do SDK de Azure ou de RabbitMQ.
- A configuração deve permitir trocar banco e storage sem alterar regras de
  negócio.
- O adaptador de objetos deve operar contra o Azurite no ambiente local e
  preservar compatibilidade com a API do Azure Blob Storage para a evolução
  planejada na `v1.1.0`.
- A `v1.0.0` deve ser totalmente executável e reproduzível sem conta,
  assinatura ou recursos de cloud provider.
- A aplicação deve ser empacotada em container; `dataset/` deve usar volume
  persistente quando o modo simples for executado em container.
- As integrações externas devem permanecer atrás de adaptadores, sem acoplar o
  domínio a SQLite, PostgreSQL, filesystem, Azurite, Azure ou RabbitMQ.

### RNF-007 — Manutenibilidade

- Código tipado, formatado e coberto por testes automatizados.
- Contratos HTTP e de evento devem ser versionados.
- Toda alteração de banco deve possuir migration reversível quando
  tecnicamente segura.
- Dependências devem ser mínimas e justificadas.

### RNF-008 — Integração contínua

- GitHub Actions deve validar pull requests e pushes para `main`.
- A instalação deve usar `uv` e o lockfile; Ruff, typos, pytest e a construção
  da imagem devem ser checks reproduzíveis.
- PostgreSQL, RabbitMQ e Azurite devem ser iniciados somente nos testes que
  realmente dependam deles.
- Workflows devem usar permissões mínimas, cache baseado no lockfile,
  cancelamento de execuções obsoletas e timeouts.
- A proteção da `main` poderá exigir checks documentados após sua definição.
- CI não implica CD. A `v1.0.0` não inclui deploy contínuo nem publicação
  automática de imagens.

## 3. Restrições

- Cada microserviço do DocPipe possui banco próprio; o Ingestion não compartilha tabelas.
- A `v1.0.0` oferece SQLite e `dataset/documents/` no modo simples, limitado a
  uma réplica com escrita.
- O laboratório compartilhado da `v1.0.0` usa PostgreSQL, Azurite e RabbitMQ
  locais e admite múltiplas réplicas da API.
- A Etapa 6 usa PostgreSQL e Azurite no laboratório local; ela não exige nem
  cria recursos Azure.
- A `v1.0.0` não inclui AKS, Azure Container Registry, Azure Database for
  PostgreSQL Flexible Server, Azure Blob Storage real, Azure Key Vault,
  Managed Identity, RBAC, rede privada, endpoints privados, ingress, domínio,
  TLS público, Azure Monitor, Application Insights ou infraestrutura cloud.
- A `v1.0.0` não inclui Kind, Kubernetes nem cluster obrigatório.
- OpenTelemetry Collector, Prometheus, Grafana, Jaeger, Tempo e Loki não são
  responsabilidades permanentes deste repositório.
- A possível troca de RabbitMQ por Azure Service Bus permanece uma decisão
  futura, não confirmada.
- O serviço não executa OCR, classificação ou extração.
- A `v1.0.0` recebe apenas um arquivo por requisição.
- Não há armazenamento público de documentos.
- Não há dados reais sensíveis nos testes acadêmicos.

## 4. Cenários mínimos de teste

| ID | Cenário | Resultado esperado |
| --- | --- | --- |
| CT-001 | PDF válido | `202`, arquivo salvo, metadados e outbox criados |
| CT-002 | PNG/JPEG válido | `202` e fluxo completo |
| CT-003 | Arquivo vazio | requisição rejeitada |
| CT-004 | Tipo não permitido | `415` e nenhuma aceitação parcial |
| CT-005 | Tamanho excedido | `413` sem crescimento ilimitado de memória |
| CT-006 | Diretório sem acesso de escrita | erro controlado e nenhum sucesso falso |
| CT-006A | Caminho malicioso no nome original | arquivo permanece dentro da raiz configurada |
| CT-007 | Broker indisponível após aceite | documento preservado e evento pendente na outbox |
| CT-008 | Reinício do publicador | evento pendente é retomado |
| CT-009 | Documento inexistente | `404` |
| CT-010 | Carga concorrente | métricas e relatório reproduzível sem perda de registros |
| CT-011 | Uma e múltiplas instâncias quando aplicável | comparação controlada sem ganho presumido |
| CT-012 | Reinício da API e do worker | recuperação sem perda de dados aceitos |
| CT-013 | PostgreSQL ou Azurite temporariamente indisponível | falha observável e recuperação/persistência verificadas |

## 5. Definição de pronto da `v1.0.0`

A `v1.0.0` estará pronta quando todos os RFs tiverem testes automatizados
relevantes; migrations SQLite e PostgreSQL forem reproduzíveis; os modos
simples e compartilhado funcionarem localmente com Docker Compose; imagens e
dependências forem verificadas; os checks de CI estiverem revisados; e não
houver segredos reais versionados. API e worker devem executar separadamente e
emitir a telemetria necessária aos experimentos.

Os testes Locust devem usar dataset sintético e registrar parâmetros,
throughput, p50, p95, p99, taxa de erro, CPU, memória, comportamento da outbox,
swap, persistência, métricas e traces. Devem cobrir indisponibilidade e
recuperação do RabbitMQ, reinícios da API e do worker e indisponibilidade
temporária do PostgreSQL ou Azurite. Nenhuma meta ou threshold será definido
antes do baseline. A revisão final deve cobrir segurança, privacidade, limites
de recursos, documentação operacional, evidências do TCC, limitações, release
candidate e preparação da tag `v1.0.0`.

## 6. Backlog da `v1.1.0`

A `v1.1.0`, sem caráter de requisito para a `v1.0.0`, fica reservada para AKS,
Azure Container Registry, Azure Database for PostgreSQL Flexible Server, Azure
Blob Storage real, Azure Key Vault, Managed Identity, RBAC, rede e endpoints
privados, ingress, domínio e TLS no Azure, infraestrutura como código, análise
FinOps, observabilidade gerenciada, políticas de backup, disponibilidade e
recuperação e validação da aplicação no ambiente Azure. Azure Service Bus
permanece apenas como possível substituto futuro do RabbitMQ a ser avaliado.

## 7. Arquitetura futura entre repositórios

Os microsserviços do DocPipe serão mantidos em repositórios separados. Cada
repositório deverá manter código, testes, CI, imagem, health checks, logs
estruturados, correlation ID, métricas, instrumentação de traces e configuração
para exportar telemetria.

Um futuro repositório integrador ou de plataforma poderá concentrar composição,
ambiente integrado, observabilidade central, dashboards, alertas, testes ponta
a ponta, experimentos integrados e infraestrutura compartilhada. Uma eventual
topologia Kubernetes também poderá ser avaliada nesse contexto. Esse
repositório ainda não está implementado nem formalmente aprovado.
