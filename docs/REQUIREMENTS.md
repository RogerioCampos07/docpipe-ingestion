# Requisitos do DocPipe Ingestion

Este documento define o escopo de entrega aprovado. A `v1.0.0` será concluída
localmente após a operação e as provas funcionais integradas da Etapa 9 e a
revisão da candidata na Etapa 10. A 10a audita requisitos e evidências; a 10b
fecha as pendências e valida a candidata final. O Compose usa PostgreSQL
próprio, Azurite e RabbitMQ, com API e worker separados. Inspeção de código,
por si só, não equivale a validação operacional; somente resultados executados
comprovam os critérios.

O DocPipe `v1.0.0` possui quatro microsserviços independentes: Ingestion,
Processing, Triage e Registry. O produto de domínio do Ingestion é o documento
aceito, armazenado e rastreável. Cada serviço mantém sua própria API HTTP.
Este repositório cobre apenas o Ingestion; RabbitMQ complementa sua API para
comunicação assíncrona e não a substitui.

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

O serviço deve preservar o arquivo original em container privado do Azurite
no ambiente de entrega da `v1.0.0`. O adaptador local existente pode permanecer
para testes e usos auxiliares, sem substituir o aceite com Azurite.

**Critérios de aceite**

- o nome físico é criado pelo sistema e não usa diretamente o nome original;
- a gravação é realizada por streaming;
- no adaptador local auxiliar, o caminho resolvido permanece na raiz
  configurada, por padrão `dataset/documents/`;
- no Azurite, a chave lógica é usada em container sem acesso público;
- o diretório não é exposto como conteúdo estático pela API;
- falha de armazenamento não produz uma resposta de sucesso.

### RF-004 — Registrar metadados

O serviço deve registrar os metadados necessários em PostgreSQL, banco
exclusivo do Ingestion e único banco operacional suportado para a `v1.0.0`.

**Critérios de aceite**

- registra UUID, nome sanitizado, tipo, tamanho, SHA-256, chave do objeto, estado e horários UTC;
- o schema é criado por migrations Alembic reproduzíveis em PostgreSQL vazio;
- o conteúdo binário não é salvo no banco relacional.

SQLite pode permanecer somente como recurso interno das fixtures existentes,
selecionado explicitamente e sem obrigação de suporte operacional. Testes
SQLite não substituem a validação de migrations, transações, constraints e
locks em PostgreSQL. Aplicar migrations de schema não implica transferir dados
SQLite; não há transferência prevista e os dados existentes serão preservados.

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
- Ensaios experimentais de carga e metas de desempenho não integram o aceite
  da `v1.0.0`. Seu planejamento seguirá a condição temporal da seção 6.

### RNF-002 — Escalabilidade

- A validação funcional da `v1.0.0` usa uma API e um worker separados em
  Docker Compose, com PostgreSQL, Azurite e RabbitMQ.
- O domínio não deve depender diretamente de um banco ou do sistema de arquivos.
- Preservar a coordenação concorrente já implementada para a outbox, sem
  exigir comparação experimental de instâncias para fechar a versão.

### RNF-003 — Confiabilidade

- Falhas do broker não podem apagar documentos já aceitos.
- Operações externas devem possuir timeout.
- O publicador deve sobreviver a reinicializações sem perder eventos pendentes.
- Deve existir caminho controlado para identificar e reenviar eventos não publicados.
- O reenvio de eventos esgotados deve preservar identificadores e payload,
  impedir alteração de eventos já publicados e registrar a ação com segurança.
- A confirmação do broker seguida de falha de commit pode causar republicação
  do mesmo `event_id`; consumidores devem tolerar repetição.
- A retomada pode exigir reinício explícito do worker após a restauração do
  broker. Esse procedimento precisa ser documentado e validado; reconexão
  automática não é requisito novo.
- Blobs órfãos e uploads incompletos devem ser identificáveis pela
  reconciliação, sem exclusão automática diante de resultado incerto.

### RNF-004 — Segurança e LGPD

- Todo tráfego de produção deve usar TLS.
- Segredos devem vir de configuração protegida da plataforma.
- Logs não podem incluir conteúdo de arquivo nem dado pessoal desnecessário.
- O acesso ao banco, aos blobs e aos volumes deve seguir menor privilégio;
  a imagem da aplicação deve executar por usuário não root.
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
- Adaptadores devem permitir a evolução de banco e storage sem alterar regras
  de negócio; isso não exige manter dois bancos operacionais suportados.
- O adaptador de objetos deve operar contra o Azurite no ambiente local e
  preservar compatibilidade com a API do Azure Blob Storage para a evolução
  planejada na `v1.1.0`.
- A `v1.0.0` deve ser totalmente executável e reproduzível sem conta,
  assinatura ou recursos de cloud provider.
- API e worker devem ser empacotados em container e executados separadamente;
  PostgreSQL, Azurite e RabbitMQ devem usar volumes persistentes no Compose.
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
- Na Etapa 9, `ci-image` valida a imagem com API e worker separados e as três
  dependências reais. Preservar os checks `ci-quality`, `ci-tests` e
  `ci-image`, cobertura e rejeição de relatórios ausentes/vazios, erros,
  falhas, skips e testes obrigatórios ausentes. O adiamento experimental não
  reduz validações funcionais.

### RNF-009 — Autonomia entre microsserviços

O DocPipe `v1.0.0` é composto por Ingestion, Processing, Triage e Registry.
Suas responsabilidades de domínio são, respectivamente: receber, validar,
registrar e armazenar o documento original; transformar o original em
representação processada e estruturada; produzir `TriageDecision` a partir de
informações processadas; e produzir `DocumentRecord`, o registro documental
estruturado final e rastreável. O Ingestion entrega um documento aceito,
armazenado e rastreável, sem executar as responsabilidades dos serviços
posteriores.

Todos os microsserviços atuais e futuros do DocPipe devem ser desacoplados,
independentes e possuir responsabilidade de negócio delimitada e utilidade
própria. Devem manter repositório, domínio, banco de dados, migrations,
configuração, testes e CI próprios. Banco, RabbitMQ e armazenamento são
dependências legítimas de infraestrutura e não precisam ser opcionais para
que o serviço seja independente. Cada um mantém também código e runtime
próprios.

O Ingestion expõe sua própria API HTTP e publica `document.received.v1` como
contrato público versionado; RabbitMQ complementa a API. O evento transporta
referências e metadados, nunca o arquivo completo, URL pública ou credenciais.
Os serviços posteriores não alteram o banco privado do Ingestion.

**Critérios de aceite do Ingestion**

- com sua infraestrutura necessária disponível e sem outros microsserviços
  em execução, recebe documento válido, responde `202`, preserva o original,
  registra metadados e outbox e permite consulta por UUID;
- publica o evento com consumidores ausentes e topologia RabbitMQ disponível,
  mantendo publisher confirms, mensagem persistente, `mandatory=True`,
  retry com backoff e entrega pelo menos uma vez;
- o aceite HTTP e o estado `PUBLISHED` não aguardam Processing nem conclusão
  de etapas posteriores; ausência de consumidores não impede inicialização,
  saúde ou execução da responsabilidade própria;
- não importa código interno, modelos ORM ou classes de domínio de outro
  serviço e não acessa diretamente seus bancos, tabelas ou filesystem interno;
- comunica-se por contratos públicos e versionados, aceitando produtores ou
  consumidores autorizados e compatíveis sem exigir implementação específica;
- instala, constrói, aplica migrations, inicia e pode ser implantado usando
  seu próprio repositório e infraestrutura, sem checkout de outro serviço;
- mantém testes próprios e CI executáveis sem outros microsserviços,
  distinguindo testes unitários, de contrato e de integração com
  infraestrutura dos testes ponta a ponta do sistema;
- permite evolução e implantação independentes com compatibilidade dos
  contratos, preservando as regras atuais dos identificadores e da publicação.

A inspeção estática anterior não identificou necessidade de refatoração para
autonomia. Não houve validação operacional naquela auditoria; os critérios
acima exigem evidências e não são uma declaração de testes aprovados.

## 3. Restrições

- Cada microserviço do DocPipe possui banco próprio; o Ingestion não compartilha tabelas.
- A `v1.0.0` entrega o serviço completo em ambiente local/portátil com Docker
  Compose, PostgreSQL próprio, Azurite e RabbitMQ. SQLite deixa de ser modo
  operacional na Etapa 9; não haverá fallback automático para ele.
- A Etapa 6 introduziu PostgreSQL e Azurite no laboratório local, preservando
  SQLite à época. Esse histórico não exige dois bancos na entrega final nem
  comprova validação atual. Não foram exigidos recursos Azure nessa etapa.
- O notebook de 8 GB deve ser considerado na execução funcional, com uma API,
  um worker e verificações sequenciais. Uma VM pode hospedar o mesmo Compose;
  isso não constitui integração com produtos Azure.
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
| CT-006 | Storage sem acesso de escrita | erro controlado e nenhum sucesso falso; Azurite no aceite e teste local existente preservado |
| CT-006A | Caminho malicioso no nome original | chave opaca no Azurite; contenção na raiz preservada nos testes do adaptador local |
| CT-007 | Broker indisponível após aceite | documento preservado e evento pendente na outbox |
| CT-008 | Reinício do publicador | evento pendente é retomado |
| CT-009 | Documento inexistente | `404` |
| CT-012 | Reinício da API e do worker | recuperação sem perda de dados aceitos |
| CT-013 | PostgreSQL ou Azurite temporariamente indisponível | falha observável e recuperação/persistência verificadas |
| CT-014 | Upload repetido com os mesmos bytes | documentos distintos e checksum igual são permitidos; sem deduplicação por checksum ou `Idempotency-Key` |
| CT-015 | Reenvio de evento esgotado não publicado | mesmos identificadores e payload, publicação pelo worker e ação registrada; evento já publicado não é alterado |
| CT-016 | Confirmação do broker seguida de falha no commit | republicação possível com o mesmo `event_id`, sem criar outro documento |
| CT-017 | Reinício das dependências e recriação de containers com volumes preservados | metadados, blobs, mensagens duráveis e eventos pendentes permanecem disponíveis |

CT-010 (carga concorrente) e CT-011 (comparação de instâncias) ficam registrados
como referências históricas retiradas do aceite da `v1.0.0`, sem renumerar os
demais casos nem apagar testes, scripts ou evidências existentes. Os casos
funcionais de falha e retomada continuam obrigatórios; não constituem ensaios
experimentais de resiliência nem campanhas de injeção de falhas.

## 5. Definição de pronto da `v1.0.0`

A Etapa 9 implementa a operação local, suas provas funcionais integradas e a
documentação. A 10a audita as evidências da candidata em
`docs/RELEASE_AUDIT.md`; a 10b corrige as pendências aprovadas e prepara o
aceite local da `v1.0.0`. O conjunto de critérios exige:

- instalação reproduzível pelas instruções do repositório, migrations em
  PostgreSQL vazio e inicialização completa em Docker Compose;
- API e worker separados, com PostgreSQL próprio, Azurite e RabbitMQ reais,
  sem mocks dessas integrações na validação integrada e sem Processing;
- conferência conjunta do original privado, SHA-256, metadados, outbox e
  mensagens publicadas conforme os contratos;
- testes de contratos, erros, duplicidade permitida, reenvio controlado,
  diagnóstico de órfãos e persistência após reinícios;
- RFs e RNFs obrigatórios vinculados a testes e evidências da revisão
  candidata, incluindo checks pertinentes aprovados no GitHub;
- imagem sem root, dependências verificadas, ausência de segredos reais e
  revisão de segurança, privacidade e instrumentação;
- `ci-image` comprova por HTTP a imagem construída, sem mounts do checkout,
  junto ao worker separado e aos serviços reais do Compose;
- documentação de instalação, configuração, execução e contratos revisada,
  versão coerente, limitações e decisão de aceite registradas.

Nenhum requisito obrigatório pendente ou validação essencial não executada
pode ser tratado como simples limitação para aceitar a versão. A validação
local da `v1.0.0` não depende de conta, infraestrutura ou validação Azure;
Azure pertence à `v1.1.0`. Tag e publicação são atos formais posteriores,
vinculados à revisão validada e sujeitos a autorização específica, assim como
commit, push, PR e merge. Seu estado deve ser registrado separadamente; não
afirmar publicação enquanto estiver pendente.

Carga e resiliência experimentais não bloqueiam esse fechamento. As evidências
históricas permanecem preservadas, sem substituir a comprovação funcional.

## 6. Backlog da `v1.1.0`

A `v1.1.0` entregará suporte aos produtos e serviços Azure, incluindo Blob
Storage e PostgreSQL, preservando a compatibilidade dos contratos públicos.
Implementação e validação desse ambiente serão planejadas posteriormente e
não são requisitos da `v1.0.0`. Azure Service Bus permanece uma decisão futura,
não confirmada.

O planejamento de carga e resiliência ocorrerá somente após a validação
funcional do Ingestion no ambiente Azure com Blob Storage e PostgreSQL. Não
se definem aqui cenários, volumes, concorrência, ferramentas ou metas.

## 7. Autonomia e composição entre repositórios

A autonomia definida no RNF-009 é obrigatória para os serviços atuais e
futuros. Cada serviço também deve manter imagem, health checks, logs
estruturados, correlation ID, métricas, instrumentação de traces e
configuração para exportar telemetria.

Um futuro repositório integrador ou de plataforma poderá concentrar composição,
ambiente integrado, observabilidade central, dashboards, alertas, testes ponta
a ponta, experimentos integrados e infraestrutura compartilhada. Uma eventual
topologia Kubernetes também poderá ser avaliada nesse contexto. Esse
repositório ainda não está implementado nem formalmente aprovado.
