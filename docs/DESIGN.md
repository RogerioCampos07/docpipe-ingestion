# Design do DocPipe Ingestion

## 1. Contexto

O DocPipe `v1.0.0` é composto por quatro microsserviços independentes:
Ingestion, Processing, Triage e Registry. O Ingestion é a fronteira de entrada
e entrega como produto de domínio um documento aceito, armazenado e
rastreável. Ele expõe sua própria API HTTP para recebimento e consulta;
RabbitMQ complementa essa API para integração assíncrona e não a substitui.
O aceite não aguarda o processamento posterior.

## 2. Objetivos arquiteturais

- responder rapidamente após a aceitação segura do documento;
- preservar o arquivo original e a rastreabilidade do fluxo;
- desacoplar recebimento e processamento por evento;
- validar o fluxo completo inicialmente em uma única instância;
- preservar adaptadores que permitam evoluir banco e storage sem alterar
  regras de negócio ou contratos públicos;
- produzir evidências funcionais e de observabilidade do serviço;
- validar localmente o armazenamento compartilhado sem depender de uma conta
  Azure;
- entregar a `v1.0.0` completa em ambiente local/portátil com Docker Compose,
  PostgreSQL próprio, Azurite e RabbitMQ, independente de cloud provider;
- manter a instrumentação independente do backend de observabilidade;
- permitir que cada microsserviço evolua em seu próprio repositório;
- preservar adaptadores e contratos que permitam evoluir para serviços Azure
  na `v1.1.0` sem acoplar o domínio.

O escopo aprovado coloca a operação local e as provas funcionais integradas
na Etapa 9, incluindo a adaptação do `ci-image`. A Etapa 10 revisa as
evidências e verifica a candidata local `v1.0.0`. Sua conclusão não depende
de Azure, reservado à `v1.1.0`; os experimentos completos são um marco
posterior à validação funcional Azure.

## 3. Fora do escopo

- OCR e extração de texto;
- normalização do documento;
- classificação do tipo de documento;
- triagem e decisão de triagem;
- interpretação de campos de negócio;
- produção do registro documental final;
- gestão de usuários e autenticação;
- relatórios e notificações;
- interface web.
- stack central de coleta, armazenamento e visualização de telemetria;
- composição operacional de todos os microsserviços;
- Kubernetes na `v1.0.0`.
- implantação Azure e ensaios experimentais de carga ou resiliência na
  `v1.0.0`; o planejamento experimental será posterior à validação funcional
  no Azure com Blob Storage e PostgreSQL.

## 4. Visão de componentes

| Componente | Responsabilidade |
| --- | --- |
| API FastAPI | Receber requisições, validar metadados e expor consultas |
| Caso de uso de ingestão | Coordenar checksum, armazenamento, persistência e resposta |
| Repositório de metadados | Isolar o acesso ao PostgreSQL próprio do serviço |
| Adaptadores de storage | Gravar no Azurite no ambiente de entrega; preservar adaptador local auxiliar |
| Tabela outbox | Registrar eventos na mesma transação dos metadados |
| Publicador de outbox | Entregar eventos pendentes ao broker e registrar tentativas |
| Broker | Desacoplar o Ingestion dos consumidores posteriores |
| Telemetria | Produzir logs, métricas e traces correlacionados |

## 5. Fluxo de ingestão

1. A API recebe `multipart/form-data` com arquivo e metadados permitidos.
2. A aplicação verifica tamanho, extensão, `Content-Type` e assinatura conhecida.
3. Durante o streaming, calcula SHA-256 e grava o arquivo no storage
   configurado, com uma chave gerada pelo sistema.
4. Em uma transação no banco configurado, grava o documento e a mensagem na
   outbox.
5. Retorna `202 Accepted` com `document_id`, estado e `correlation_id`.
6. Um publicador separado lê a outbox e envia `document.received.v1` ao broker.
7. Após confirmação do broker, marca a mensagem como publicada.

Se o arquivo for gravado, mas a transação falhar, ele se torna órfão e deverá
ser identificado por uma rotina de reconciliação. O arquivo não deve ser
apagado automaticamente durante uma falha incerta.

## 6. Armazenamento local

O adaptador local foi implementado nas etapas iniciais e pode permanecer
para testes e usos auxiliares. O aceite da `v1.0.0` exige Azurite; as regras
abaixo descrevem o adaptador existente, sem criar outro percurso de release.

- A raiz padrão é `dataset/documents/` e deve ser configurável.
- A chave física é gerada pelo serviço e não deriva diretamente do nome enviado
  pelo cliente.
- O caminho resolvido deve permanecer dentro da raiz configurada.
- O nome original sanitizado existe apenas como metadado para exibição.
- Os arquivos recebidos não devem ser versionados no Git.
- Escritas devem usar arquivo temporário e renomeação atômica quando possível,
  evitando que arquivos parciais sejam tratados como válidos.
- O adaptador local respeita a mesma interface do adaptador de objetos
  introduzido na Etapa 6.

## 7. Persistência e transição para PostgreSQL

SQLite em `dataset/docpipe-ingestion.db` foi o modo padrão das etapas iniciais,
com chaves estrangeiras, timeout de bloqueio e configuração de WAL. O modo
operacional atual usa PostgreSQL e Azurite por padrão. O suporte PostgreSQL
inclui `psycopg[binary]`, engine SQLAlchemy, migrations Alembic, serviço
Compose com volume e `tests/integration/test_postgresql.py`.
O alcance das provas operacionais está em `docs/RELEASE_AUDIT.md`.

Os defaults operacionais da Etapa 9 passaram a PostgreSQL e Azurite, sem
fallback silencioso. SQLite pode permanecer apenas nas fixtures internas
existentes, selecionado explicitamente, sem substituir testes reais de
transações, constraints, locks e migrations PostgreSQL. Não há necessidade
identificada de novo driver nem de redesenhar tabelas.

Reutiliza-se a cadeia Alembic existente até `20260918_03`; sua aplicação em
PostgreSQL vazio foi exercitada no CI da revisão auditada. Revisões novas
somente se uma correção exigir mudança de schema. Aplicar migrations não
transfere dados SQLite: não há transferência prevista e os arquivos e
volumes existentes devem ser preservados.

## 8. Modelo de dados inicial

### `documents`

| Campo | Descrição |
| --- | --- |
| `id` | UUID público do documento |
| `original_name` | Nome original sanitizado para exibição |
| `media_type` | Tipo detectado/validado |
| `size_bytes` | Tamanho recebido |
| `sha256` | Checksum hexadecimal |
| `storage_key` | Chave opaca do blob privado; relativa à raiz no adaptador local auxiliar |
| `status` | Estado atual da ingestão |
| `correlation_id` | Correlação ponta a ponta |
| `created_at` | Data/hora UTC de criação |
| `updated_at` | Data/hora UTC da última atualização |

### `outbox_events`

| Campo | Descrição |
| --- | --- |
| `id` | UUID do evento |
| `aggregate_id` | UUID do documento |
| `event_type` | Nome versionado do evento |
| `payload` | Corpo JSON validado |
| `created_at` | Data/hora UTC de criação |
| `published_at` | Data/hora de publicação, quando houver |
| `attempts` | Número de tentativas |
| `last_error` | Erro técnico resumido e sem dado sensível |

## 9. Contrato HTTP inicial

### `POST /v1/documents`

- Entrada: arquivo e metadados opcionais previstos pelo schema.
- Sucesso: `202 Accepted`.
- Resposta mínima: `document_id`, `status`, `correlation_id`, `received_at`.
- Erros esperados: `400` para requisição inválida, `413` para tamanho excedido, `415` para tipo não suportado e `503` quando uma dependência essencial impedir a aceitação segura.

Repetições causadas por timeout poderão ser controladas posteriormente por `Idempotency-Key`. O checksum serve para integridade e diagnóstico, não deve ser usado sozinho para rejeitar documentos duplicados.

Na `v1.0.0`, uploads repetidos podem gerar documentos distintos, com novos
UUIDs e checksum igual. A republicação da outbox mantém o mesmo `event_id`.
O fechamento verifica esses comportamentos sem introduzir deduplicação nova.

### `GET /v1/documents/{document_id}`

- Retorna somente metadados pertencentes ao Ingestion.
- Não devolve o arquivo nem URL pública nesta versão.
- Retorna `404` quando o identificador não existe ou não é visível no contexto de acesso.

## 10. Evento `document.received.v1`

Envelope mínimo:

```json
{
  "event_id": "uuid",
  "event_type": "document.received",
  "event_version": 1,
  "occurred_at": "data-hora UTC em ISO 8601",
  "correlation_id": "uuid",
  "document_id": "uuid",
  "data": {
    "storage_key": "string",
    "media_type": "application/pdf",
    "size_bytes": 12345,
    "sha256": "hexadecimal"
  }
}
```

O evento não deve conter o conteúdo do arquivo, URL pública nem credencial de acesso.

## 11. Confiabilidade

- O padrão transactional outbox evita perder o evento após confirmar a gravação no banco.
- A entrega é **pelo menos uma vez**; consumidores devem ser idempotentes.
- O publicador utiliza retry com backoff e limite configurável.
- Após esgotar tentativas, o evento permanece identificável para diagnóstico e reprocessamento controlado.
- Timeouts devem ser explícitos para banco, storage e broker.
- A escrita do blob e a transação PostgreSQL não formam uma única transação;
  arquivos órfãos devem ser detectáveis e reconciliáveis.

O diagnóstico por correlação e a reconciliação são somente leitura. O comando
operacional de reenvio da Etapa 9 aceita evento não publicado esgotado,
preserva IDs e payload, usa atualização condicional para rejeitar concorrência
com publicação e registra a ação sem conteúdo do evento. A reconciliação
identifica órfãos e uploads incompletos sem exclusão automática.

O worker observa o canal RabbitMQ no próprio thread que o utiliza. Quando o
canal fecha, ele deixa de reportar readiness, registra a falha e encerra com
estado não zero, preservando eventos não publicados na outbox. Após restaurar
RabbitMQ, o operador reinicia explicitamente o worker; eventos esgotados também
exigem reenvio. Reconexão automática não é requisito. A prova funcional local
deve validar essa recuperação, sem campanhas experimentais de falhas.

## 12. Segurança e privacidade

- Blobs, banco e volumes são privados. Arquivos locais auxiliares também não
  podem ser expostos pelo servidor HTTP como conteúdo estático.
- As permissões locais devem restringir o acesso ao usuário do processo.
- TLS é obrigatório fora do ambiente local.
- O serviço aplica limite de requisição e de tamanho de arquivo.
- O conteúdo do documento nunca aparece em logs, métricas ou traces.
- Metadados pessoais devem ser mínimos e possuir política futura de retenção e exclusão compatível com LGPD.
- Varredura antimalware pode ser incorporada posteriormente como etapa assíncrona dedicada.

## 13. Observabilidade

### Logs

JSON estruturado com `timestamp`, `level`, `service`, `environment`, `correlation_id`, `trace_id`, `operation`, `status` e `duration_ms`.

### Métricas mínimas

- total de requisições e uploads aceitos/rejeitados;
- latência HTTP por rota e status;
- bytes recebidos;
- duração e falhas de banco, storage e broker;
- eventos pendentes e idade do evento mais antigo na outbox;
- tentativas e falhas de publicação.

### Traces

Span da requisição e spans filhos para armazenamento, transação no banco e publicação. Propagar W3C Trace Context quando suportado.

### Decisões implementadas na Etapa 7

- `correlation_id` permanece o identificador funcional e é propagado por
  `ContextVar`; trace e correlação não são derivados um do outro;
- `document.received.v1` permanece inalterado. O carrier W3C é persistido em
  coluna privada nullable da outbox e enviado em headers AMQP;
- a API expõe `/metrics`; o worker possui servidor separado em porta
  configurável;
- a readiness da API consulta banco e storage. RabbitMQ e exporters não são
  dependências de aceitação devido à outbox transacional;
- métricas são expostas para scrape e traces podem ser exportados por OTLP
  HTTP a um endpoint configurável; logs são emitidos em stderr. Não há
  exporter OTLP de métricas ou logs configurado pela aplicação;
- identificadores individuais aparecem somente em logs e traces quando
  necessários ao diagnóstico, nunca como labels Prometheus.

OpenTelemetry Collector, Prometheus, Grafana, Jaeger, Tempo, Loki, dashboards,
alertas e armazenamento central não pertencem à arquitetura permanente deste
repositório. O Compose, as configurações e o dashboard centrais de Prometheus,
Grafana e Tempo foram removidos na refatoração preparatória à Etapa 8.
A referência histórica está em `docs/OBSERVABILITY.md`. Os SDKs, exporters,
endpoints e a propagação da Etapa 7 permanecem.

O encerramento do provider usa uma única thread daemon de limpeza e um prazo
compartilhado entre chamadas, inclusive no encerramento do processo. Essa
thread é iniciada junto ao provider, pois Python não permite iniciá-la em
`atexit`. O shutdown do SDK drena os lotes; não é precedido por `force_flush`,
cujo timeout não é aplicado pelo processador da versão fixada no lockfile.
Depois do prazo configurado, o processo pode terminar com perda de spans
pendentes. Essa perda não altera documentos, eventos ou confirmação do broker.

## 14. Execução local da `v1.0.0`

Os itens abaixo definem a operação local da `v1.0.0`. O Compose principal
contém as dependências, um serviço de setup para migrations e preparação de
blobs, API e worker separados. A prova integrada da Etapa 9 deve confirmar
esses comportamentos contra a imagem construída e as dependências reais.

- Imagem Docker executada por usuário não root.
- Configuração via variáveis de ambiente, validada na inicialização.
- Segredos fornecidos pela plataforma, nunca incluídos na imagem.
- PostgreSQL próprio, Azurite e RabbitMQ executam no Docker Compose principal
  e preservam metadados/outbox, blobs e mensagens duráveis em volumes.
- API e worker executam como processos separados.
- A imagem é construída e validada localmente e pelo CI, sem publicação
  automática.
- Readiness considera dependências necessárias para aceitar documentos com segurança; liveness verifica apenas o processo.
- Migrações são executadas de forma controlada, não simultaneamente por todas
  as instâncias.
- A validação funcional considera o notebook de 8 GB, uma API, um worker e
  execução sequencial dos checks, sem gerador de carga ou stack central.
- Uma VM pode hospedar o mesmo Compose; isso não constitui integração com
  produtos Azure nem autoriza criar infraestrutura.
- Reinícios e recriação de containers com volumes preservados devem manter
  documentos aceitos e eventos pendentes. Testes que limpam tabelas e filas
  usam recursos descartáveis separados das evidências.

Kind e Kubernetes não fazem parte da `v1.0.0`. A versão é um serviço completo
e validado localmente, sem alegação de implantação de produção. O fechamento
ocorre na Etapa 10, conforme a definição de pronto em `REQUIREMENTS.md`; atos
de Git, tag e publicação exigem autorização própria.

## 15. Evolução implementada na Etapa 6

Para os experimentos com múltiplas réplicas, foram adicionados:

- PostgreSQL como alternativa ao SQLite;
- armazenamento de objetos compartilhado como alternativa a
  `dataset/documents/`, usando
  Azurite no laboratório local.

Esse é o histórico da Etapa 6. A decisão posterior de adotar PostgreSQL como
único banco operacional da entrega está na seção 7; não desfaz o trabalho
anterior nem presume que os testes passaram na revisão atual.

O adaptador de objetos utiliza a API do Azure Blob Storage contra o Azurite.
Assim, os testes locais não exigem assinatura, credenciais ou recursos Azure.
O Azure Blob Storage real pertence à entrega futura da `v1.1.0`; sua
configuração, autenticação, RBAC e validação não pertencem à Etapa 6 local.

As trocas devem ocorrer por adaptadores, sem alterar as regras de domínio nem
os contratos HTTP e de eventos. O RabbitMQ permanece como broker nesta etapa;
uma eventual adoção do Azure Service Bus exige decisão e etapa próprias.

## 16. Decisões registradas

| Decisão | Motivo |
| --- | --- |
| Autonomia obrigatória de cada microsserviço | Preserva utilidade própria, execução, evolução e implantação independentes; fronteiras na seção 19 |
| Resposta `202 Accepted` | O processamento continua de forma assíncrona |
| `v1.0.0` independente de cloud | Garante laboratório reproduzível sem conta, assinatura ou recursos externos |
| SQLite no modo simples, decisão histórica | Serviu às etapas iniciais; na entrega final fica restrito ao uso interno de testes |
| Arquivos em `dataset/documents/`, adaptador existente | Preserva testes e usos auxiliares; Azurite é obrigatório no aceite da versão |
| PostgreSQL como único banco operacional | Consolida o percurso de entrega e evita suporte obrigatório a dois bancos |
| Banco privado do serviço | Preserva autonomia e evita acoplamento entre microserviços |
| Transactional outbox | Reduz a janela de inconsistência entre banco e broker |
| PostgreSQL, Azurite e RabbitMQ locais | Fornecem infraestrutura compartilhada para o laboratório da `v1.0.0` |
| Broker atrás de adaptador | Preserva portabilidade; RabbitMQ continua confirmado na `v1.0.0` |
| Azurite na Etapa 6 | Valida localmente o adaptador de objetos compatível com Azure Blob sem exigir conta Azure |
| GitHub Actions na Etapa 8 | Valida mudanças continuamente sem implicar deploy contínuo |
| Docker Compose na Etapa 9 e revisão na Etapa 10 | Consolida e comprova a operação local; a etapa seguinte revisa evidências da candidata |
| Experimentos adiados | Planejamento somente após validação funcional Azure com Blob Storage e PostgreSQL; histórico preservado |
| Azure na `v1.1.0` | Separa a validação local da implantação e integração com serviços gerenciados |
| Azure Service Bus não decidido | Mantém sua possível adoção como avaliação futura |
| Contratos versionados | Facilita evolução independente de produtores e consumidores |

## 17. Persistência compartilhada local

A Etapa 6 implementou composição explícita dos adaptadores, preservando
SQLite e filesystem no modo simples à época. O percurso operacional aprovado
usa PostgreSQL, Azurite e RabbitMQ, com defaults e Compose principal alinhados
na Etapa 9. SQLite e filesystem permanecem em testes auxiliares; os contratos
públicos permanecem.

No PostgreSQL, cada worker seleciona um evento elegível com
`FOR UPDATE SKIP LOCKED`, mantendo o lock durante a publicação confirmada. O
sucesso atualiza evento e documento antes do commit. A falha incrementa a
tentativa e persiste `next_attempt_at` com backoff. Uma confirmação do RabbitMQ
seguida de falha de commit ainda pode produzir duplicidade com o mesmo
`event_id`; a entrega continua sendo pelo menos uma vez.

O adaptador `AzureBlobDocumentStorage` usa a API Azure Blob contra o Azurite.
Ele envia blocos limitados, confirma o blob somente após consumir o stream e
preserva `storage_key`, SHA-256, tamanho e tipo. Marcadores privados em
`_uploads/` permitem identificar uploads incompletos. A reconciliação compara
as chaves completas com o banco e apenas relata órfãos; nenhuma falha incerta
causa exclusão automática.

O Azurite valida as operações de blobs usadas no laboratório. Não valida
Managed Identity, RBAC, rede privada, disponibilidade, redundância, desempenho
ou equivalência total com Azure Blob Storage. A compatibilidade de API não
significa que a `v1.0.0` foi implantada ou validada no Azure.

### Laboratório experimental histórico

O laboratório foi implementado sob o escopo anterior da Etapa 9. Seus scripts,
workflows, relatórios e evidências são preservados; sua existência não
comprova ensaios concluídos nem condiciona o fechamento funcional da versão.
Os detalhes abaixo descrevem o mecanismo existente, sem planejar novos
ensaios. O estado das evidências está em `docs/EXPERIMENTS.md`.

Cada execução de carga ou resiliência possui projeto Docker Compose, banco,
container Blob e fila RabbitMQ próprios. Um Locust na mesma máquina alterna
requisições entre duas APIs por endereço interno, quando solicitado, e mede o
HTTP separadamente da drenagem da outbox. Duas APIs dividem um orçamento fixo
de CPU e memória; dois workers disputam eventos no PostgreSQL com o mecanismo
de lock já implementado. Não se presume ganho por replicação.

O worker atual não reconecta sozinho ao RabbitMQ após perder seu canal. Nos
experimentos, a recuperação do broker inclui reinício explícito do worker.
Eventos que esgotem tentativas ficam identificáveis e não são reativados
automaticamente. Essa limitação operacional é preservada nas evidências; a
entrega do evento continua sendo pelo menos uma vez. Coleta de logs, métricas
e snapshots ocorre sem stack central ou receptor OTLP obrigatório.

## 18. Evolução Azure na `v1.1.0`

A `v1.1.0` entregará suporte aos produtos e serviços Azure, incluindo Blob
Storage e PostgreSQL, preservando os contratos públicos. Sua implementação
será planejada posteriormente; não há implantação cloud nas Etapas 9 e 10.
A possível substituição do RabbitMQ por Azure Service Bus continua em
avaliação e não é uma decisão arquitetural confirmada.

Os adaptadores existentes preservam portabilidade, mas o Azurite não equivale
ao Azure Blob Storage real. Autenticação, autorização, rede, disponibilidade
e operação dos serviços gerenciados exigem validação no ambiente Azure futuro.

Somente após a validação funcional do Ingestion no ambiente Azure com Blob
Storage e PostgreSQL ocorrerá o planejamento de carga e resiliência. Não são
definidos agora cenários, volumes, concorrência, ferramentas ou metas.

## 19. Autonomia obrigatória dos microsserviços

É uma determinação arquitetural obrigatória do DocPipe: todos os
microsserviços atuais e futuros devem ser desacoplados dos demais,
independentes e possuir utilidade própria. Cada serviço deve:

- ter responsabilidade de negócio delimitada e executá-la sem exigir outros
  microsserviços em execução;
- manter repositório, domínio, banco de dados, migrations, configuração,
  testes e CI próprios, além de imagem, health checks e instrumentação;
- comunicar-se por contratos públicos e versionados, aceitando produtores ou
  consumidores autorizados e compatíveis sem depender de implementações
  específicas;
- permitir evolução e implantação independentes, respeitando a
  compatibilidade dos contratos.

Na arquitetura `v1.0.0`, as fronteiras de domínio são:

Cada serviço expõe sua própria API HTTP, além de se comunicar por contratos
públicos versionados quando integra outros serviços.

- **Ingestion:** recebe, valida, registra e armazena o documento original,
  entregando um documento aceito, armazenado e rastreável;
- **Processing:** transforma o documento original em uma representação
  processada e estruturada;
- **Triage:** produz uma `TriageDecision` a partir de informações processadas;
- **Registry:** produz o `DocumentRecord`, registro documental estruturado
  final e rastreável.

Essa delimitação não especifica a implementação interna dos serviços
posteriores. O Ingestion mantém sua API HTTP própria e publica
`document.received.v1` como contrato público versionado; RabbitMQ complementa
a API para comunicação assíncrona. O evento transporta referências e
metadados, não o arquivo completo, URL pública ou credenciais. O aceite e a
conclusão da operação própria do Ingestion não dependem da execução de
Processing, Triage ou Registry.

É proibido importar código interno, modelos ORM ou classes de domínio de
outro serviço, acessar diretamente seus bancos ou tabelas ou usar seu
filesystem interno. Instalação, build, migrations, inicialização e validação
do serviço devem ser possíveis sem checkout de outro microsserviço.

### Dependências permitidas e fronteira do Ingestion

Banco, RabbitMQ e armazenamento são dependências legítimas de infraestrutura.
Independência entre microsserviços não significa ausência dessas dependências
nem exige torná-las opcionais. Compartilhar infraestrutura não autoriza
acesso ao estado interno de outro serviço. No laboratório, as réplicas do
Ingestion compartilham seu banco PostgreSQL e seu storage Azurite; o banco
continua privado ao Ingestion.

Os serviços posteriores não alteram o banco privado do Ingestion. Nenhum
serviço importa código interno, modelos, banco de dados ou runtime de outro;
cada um mantém repositório, domínio, persistência, configuração, testes e CI
próprios, com evolução independente por contratos públicos versionados.

Receber, registrar e armazenar documentos constitui uma capacidade própria,
com consulta de metadados e estado da ingestão. Ela não exige Processing nem
a conclusão de etapas posteriores. O `202` segue condicionado ao arquivo
armazenado e ao commit conjunto do documento e da outbox. O worker publica
`document.received.v1` com mensagem persistente, publisher confirms e
`mandatory=True`, declarando exchange, fila durável e binding. `PUBLISHED`
indica publicação confirmada pelo broker, sem esperar resposta de consumidor.
Ausência de consumidores não equivale a ausência da topologia de entrega.

Permanecem a entrega pelo menos uma vez, retry com backoff e limite de
tentativas, bem como as regras de `event_id`, `document_id` e
`correlation_id`. A referência pública `storage_key` identifica um objeto no
storage configurado; não concede acesso ao banco ou ao filesystem interno,
nem contém URL pública ou credencial. Integrações com storage compartilhado
devem usar sua API e autorização, respeitando o contrato do evento.

A readiness da API depende de banco e storage; a do worker depende de banco
e conexão/canal RabbitMQ. Nenhuma depende da presença ou resposta de
Processing ou de um consumidor específico.

### Decisão e evidências

A auditoria anterior concluiu, por inspeção estática do repositório, que o
Ingestion atende à diretriz e não necessita de refatoração para autonomia.
Essa auditoria não executou testes, build ou infraestrutura e não realizou
validação operacional. A determinação é obrigatória; sua comprovação em
execução exige evidências pelos critérios do RNF-009 de `REQUIREMENTS.md`.
O registro documental não conclui a Etapa 9 nem altera as pendências do plano.

### Composição futura

Um futuro repositório integrador ou de plataforma poderá compor os serviços,
operar infraestrutura compartilhada, hospedar a stack central de
observabilidade e executar testes ponta a ponta ou integrados. Também poderá
avaliar uma topologia Kubernetes, inclusive Kind para integração local. Esse
repositório ainda não foi criado e sua arquitetura não está definida. A
separação de responsabilidades está aprovada; a implementação permanece
futura. A composição sistêmica, observabilidade central, cloud provider e
Kubernetes não pertencem ao escopo deste repositório nem ao fechamento local
e portátil da `v1.0.0`.
