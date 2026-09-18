# Design do DocPipe Ingestion

## 1. Contexto

O DocPipe processa documentos corporativos por meio de microserviços independentes. O Ingestion é a fronteira de entrada do pipeline e deve aceitar picos de upload sem acoplar a resposta HTTP ao processamento posterior.

## 2. Objetivos arquiteturais

- responder rapidamente após a aceitação segura do documento;
- preservar o arquivo original e a rastreabilidade do fluxo;
- desacoplar recebimento e processamento por evento;
- validar o fluxo completo inicialmente em uma única instância;
- preservar fronteiras que permitam trocar SQLite e storage local antes da
  escala horizontal;
- produzir evidências de desempenho e observabilidade para o TCC;
- validar localmente o armazenamento compartilhado sem depender de uma conta
  Azure.

## 3. Fora do escopo

- OCR e extração de texto;
- classificação do tipo de documento;
- interpretação de campos de negócio;
- gestão de usuários e autenticação;
- relatórios e notificações;
- interface web.

## 4. Visão de componentes

| Componente | Responsabilidade |
| --- | --- |
| API FastAPI | Receber requisições, validar metadados e expor consultas |
| Caso de uso de ingestão | Coordenar checksum, armazenamento, persistência e resposta |
| Repositório de metadados | Isolar o acesso ao SQLite |
| Adaptador de storage local | Gravar o original em `dataset/documents/` |
| Tabela outbox | Registrar eventos na mesma transação dos metadados |
| Publicador de outbox | Entregar eventos pendentes ao broker e registrar tentativas |
| Broker | Desacoplar o Ingestion dos consumidores posteriores |
| Telemetria | Produzir logs, métricas e traces correlacionados |

## 5. Fluxo de ingestão

1. A API recebe `multipart/form-data` com arquivo e metadados permitidos.
2. A aplicação verifica tamanho, extensão, `Content-Type` e assinatura conhecida.
3. Durante o streaming, calcula SHA-256 e grava o arquivo em
   `dataset/documents/` com uma chave gerada pelo sistema.
4. Em uma transação SQLite, grava o documento e a mensagem na outbox.
5. Retorna `202 Accepted` com `document_id`, estado e `correlation_id`.
6. Um publicador separado lê a outbox e envia `document.received.v1` ao broker.
7. Após confirmação do broker, marca a mensagem como publicada.

Se o arquivo for gravado, mas a transação falhar, ele se torna órfão e deverá
ser identificado por uma rotina de reconciliação. O arquivo não deve ser
apagado automaticamente durante uma falha incerta.

## 6. Armazenamento local

- A raiz padrão é `dataset/documents/` e deve ser configurável.
- A chave física é gerada pelo serviço e não deriva diretamente do nome enviado
  pelo cliente.
- O caminho resolvido deve permanecer dentro da raiz configurada.
- O nome original sanitizado existe apenas como metadado para exibição.
- Os arquivos recebidos não devem ser versionados no Git.
- Escritas devem usar arquivo temporário e renomeação atômica quando possível,
  evitando que arquivos parciais sejam tratados como válidos.
- O adaptador local deve respeitar a mesma interface que permitirá adotar
  armazenamento de objetos futuramente.

## 7. Persistência SQLite

O arquivo SQLite fica, por padrão, em `dataset/docpipe-ingestion.db`, com caminho
configurável por variável de ambiente. O serviço deve habilitar chaves
estrangeiras e configurar timeout de bloqueio. O modo WAL será usado quando
validado pelos testes do ambiente alvo.

SQLite atende à primeira versão de instância única. Ele não deve ser apresentado
como banco adequado para várias réplicas gravando concorrentemente.

## 8. Modelo de dados inicial

### `documents`

| Campo | Descrição |
| --- | --- |
| `id` | UUID público do documento |
| `original_name` | Nome original sanitizado para exibição |
| `media_type` | Tipo detectado/validado |
| `size_bytes` | Tamanho recebido |
| `sha256` | Checksum hexadecimal |
| `storage_key` | Caminho relativo e opaco dentro da raiz de documentos |
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
- Timeouts devem ser explícitos para SQLite e broker.
- A escrita do arquivo e a transação SQLite não formam uma única transação;
  arquivos órfãos devem ser detectáveis e reconciliáveis.

## 12. Segurança e privacidade

- `dataset/documents/` e o arquivo SQLite não podem ser expostos pelo servidor
  HTTP como diretórios estáticos.
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
- duração e falhas de SQLite, sistema de arquivos e broker;
- eventos pendentes e idade do evento mais antigo na outbox;
- tentativas e falhas de publicação.

### Traces

Span da requisição e spans filhos para armazenamento, transação no banco e publicação. Propagar W3C Trace Context quando suportado.

## 14. Implantação

- Imagem Docker executada por usuário não root.
- Configuração via variáveis de ambiente, validada na inicialização.
- Segredos fornecidos pela plataforma, nunca incluídos na imagem.
- A primeira versão executa com uma única réplica e usa volume persistente para
  `dataset/` quando estiver em container.
- A escala horizontal exige substituir SQLite e storage local por serviços
  compartilhados apropriados.
- Readiness considera dependências necessárias para aceitar documentos com segurança; liveness verifica apenas o processo.
- Migrações são executadas como tarefa controlada de implantação, não simultaneamente por todas as réplicas.

## 15. Evolução implementada na Etapa 6

Para os experimentos com múltiplas réplicas, foram adicionados:

- PostgreSQL como alternativa ao SQLite;
- armazenamento de objetos compartilhado como alternativa a
  `dataset/documents/`, usando
  Azurite no laboratório local.

O adaptador de objetos utiliza a API do Azure Blob Storage contra o Azurite.
Assim, os testes locais não exigem assinatura, credenciais ou recursos Azure.
O Azure Blob Storage real permanece como destino futuro possível, mas sua
configuração, autenticação, RBAC e validação não pertencem à Etapa 6 local.

As trocas devem ocorrer por adaptadores, sem alterar as regras de domínio nem
os contratos HTTP e de eventos. O RabbitMQ permanece como broker nesta etapa;
uma eventual adoção do Azure Service Bus exige decisão e etapa próprias.

## 16. Decisões registradas

| Decisão | Motivo |
| --- | --- |
| Resposta `202 Accepted` | O processamento continua de forma assíncrona |
| SQLite na primeira versão | Reduz infraestrutura e simplifica o desenvolvimento local |
| Arquivos em `dataset/documents/` | Permite validar o fluxo sem serviço externo de storage |
| Banco privado do serviço | Preserva autonomia e evita acoplamento entre microserviços |
| Transactional outbox | Reduz a janela de inconsistência entre banco e broker |
| Broker atrás de adaptador | Permite laboratório local e implantação Azure |
| Azurite na Etapa 6 | Valida localmente o adaptador de objetos compatível com Azure Blob sem exigir conta Azure |
| Contratos versionados | Facilita evolução independente de produtores e consumidores |

## 17. Persistência compartilhada local

A Etapa 6 implementa composição explícita dos adaptadores. SQLite e filesystem
continuam sendo o modo simples. PostgreSQL e Azurite formam o laboratório
compartilhado; RabbitMQ e os contratos públicos permanecem iguais.

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
ou equivalência total com Azure Blob Storage. Azure real permanece futuro.
