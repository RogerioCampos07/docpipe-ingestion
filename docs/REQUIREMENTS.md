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

O serviço deve preservar o arquivo original no diretório local
`dataset/documents/`.

**Critérios de aceite**

- o nome físico é criado pelo sistema e não usa diretamente o nome original;
- a gravação é realizada por streaming;
- o caminho resolvido permanece dentro de `dataset/documents/`;
- o diretório não é exposto como conteúdo estático pela API;
- falha de armazenamento não produz uma resposta de sucesso.

### RF-004 — Registrar metadados

O serviço deve registrar os metadados necessários em seu próprio banco SQLite.

**Critérios de aceite**

- registra UUID, nome sanitizado, tipo, tamanho, SHA-256, chave do objeto, estado e horários UTC;
- o schema é criado e evoluído por migrations compatíveis com SQLite;
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

**Estado:** implementado com RabbitMQ no laboratório local e publicador
executado separadamente da API.

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
- métricas podem ser coletadas pelo Prometheus;
- nenhum endpoint expõe segredo ou conteúdo de documento.

## 2. Requisitos não funcionais

### RNF-001 — Desempenho

- O upload deve utilizar streaming e memória limitada por requisição.
- A API não deve aguardar OCR ou processamento posterior.
- O experimento de carga deve medir percentis p50, p95 e p99, throughput e taxa de erro.
- Metas numéricas finais serão definidas após um teste de baseline documentado; não devem ser inventadas previamente.

### RNF-002 — Escalabilidade

- A primeira versão deve operar corretamente em uma única instância.
- O domínio não deve depender diretamente de SQLite nem do sistema de arquivos.
- A evolução para múltiplas réplicas exige PostgreSQL e armazenamento de objetos
  compartilhado ou soluções equivalentes.

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

### RNF-006 — Portabilidade

- O domínio e os casos de uso não devem depender diretamente de SQLite, do
  sistema de arquivos, do SDK de Azure ou de RabbitMQ.
- A configuração deve permitir trocar banco e storage sem alterar regras de
  negócio.
- A aplicação deve ser empacotada em container; `dataset/` deve usar volume
  persistente quando a primeira versão for executada em container.

### RNF-007 — Manutenibilidade

- Código tipado, formatado e coberto por testes automatizados.
- Contratos HTTP e de evento devem ser versionados.
- Toda alteração de banco deve possuir migration reversível quando tecnicamente segura.
- Dependências devem ser mínimas e justificadas.

## 3. Restrições

- Cada microserviço do DocPipe possui banco próprio; o Ingestion não compartilha tabelas.
- A primeira versão usa SQLite e armazenamento em `dataset/documents/`.
- A primeira versão é limitada a uma única réplica com escrita.
- O serviço não executa OCR, classificação ou extração.
- A primeira versão recebe apenas um arquivo por requisição.
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

## 5. Definição de pronto da primeira versão

A primeira versão estará pronta quando todos os RFs tiverem testes automatizados
relevantes, as migrations SQLite forem reproduzíveis, o fluxo funcionar no
ambiente local, os documentos forem persistidos com segurança em
`dataset/documents/`, a imagem de container passar nas verificações, a
telemetria for coletável e um teste de carga de instância única puder ser
repetido.
