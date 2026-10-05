# Tutorial prático — DocPipe Ingestion v1.0.0

Este tutorial mostra como executar localmente o Ingestion com Docker Compose,
enviar um documento e consultar o estado da ingestão.

## Visão geral

O Ingestion recebe PDFs, PNGs e JPEGs, valida o arquivo, armazena o original
privadamente, registra metadados e cria o evento inicial
`document.received.v1`. A execução local reúne PostgreSQL, Azurite, RabbitMQ,
uma API HTTP e um worker da outbox.

O serviço não executa OCR, classificação, triagem nem registro documental
final. Processing, Triage e Registry são microsserviços independentes, com
responsabilidades próprias; eles não são iniciados nem integrados por este
tutorial.

## Pré-requisitos

Instale Git, Docker Engine com o plugin Docker Compose e `curl`. Confira as
instalações:

```bash
git --version
docker --version
docker compose version
curl --version
```

O daemon do Docker também precisa estar iniciado e acessível pelo seu usuário.

## Preparação

Se o repositório ainda não estiver disponível localmente, clone-o pelo endereço
fornecido pela sua equipe. Em seguida, entre na pasta do repositório:

```bash
cd docpipe-ingestion
```

Confirme a versão declarada pelo pacote:

```bash
grep '^version = ' pyproject.toml
```

O resultado esperado é `version = "1.0.0"`. O Compose principal está em
`docker-compose.yml`; as variáveis e portas locais estão listadas em
`.env.example`. Crie o arquivo local usado pelo Compose:

```bash
if [ ! -f .env ]; then cp .env.example .env; fi
```

Os valores padrão de `.env.example` são exclusivos do ambiente local de
desenvolvimento. Não os reutilize em ambientes compartilhados ou de produção,
nem versione o arquivo `.env`.

## Inicialização

Baixe as imagens de infraestrutura e inicie os serviços de banco, blobs e
mensageria. O comando aguarda os health checks do Compose:

```bash
docker compose pull postgres rabbitmq azurite
docker compose up -d --wait postgres azurite
docker compose up -d --wait rabbitmq
```

Execute o serviço de preparação uma vez. Ele aplica as migrations do
PostgreSQL e cria o container privado de blobs no Azurite:

```bash
docker compose --profile setup run --build --rm setup
```

Agora construa e inicie a API e o worker em containers separados:

```bash
docker compose up -d --build --wait
docker compose ps
```

O papel de cada serviço é:

- **PostgreSQL:** guarda os metadados do Ingestion e a outbox transacional.
- **Azurite:** emula localmente o armazenamento privado de blobs.
- **RabbitMQ:** recebe os eventos publicados pelo worker.
- **API:** recebe uploads HTTP e oferece consulta de metadados.
- **Worker:** publica eventos pendentes da outbox no RabbitMQ.
- **setup:** aplica migrations e prepara o armazenamento antes da aplicação.

Por padrão, as portas publicadas pelo Compose escutam somente em `127.0.0.1`.
`docker compose ps` mostra estado e saúde dos containers. Confira as rotas de
saúde da API e do worker:

```bash
curl --fail --show-error http://127.0.0.1:8000/health/live
curl --fail --show-error http://127.0.0.1:8000/health/ready
curl --fail --show-error http://127.0.0.1:9001/health/ready
```

Liveness verifica se o processo da API está ativo. A readiness da API exige
PostgreSQL e Azurite disponíveis; a do worker exige PostgreSQL e RabbitMQ.
Consulte logs de um serviço específico com:

```bash
docker compose logs --tail=100 api
docker compose logs --tail=100 worker
```

## Primeiro upload

Crie um PDF sintético mínimo em `/tmp`; ele não é adicionado ao repositório:

```bash
printf '%%PDF-1.7\nDocumento sintético para teste local.\n' \
  > /tmp/docpipe-exemplo.pdf
```

Confirme novamente que a API aceita requisições e envie o arquivo no campo
multipart `file`:

```bash
curl --fail --show-error http://127.0.0.1:8000/health/ready
curl --include --show-error \
  -F 'file=@/tmp/docpipe-exemplo.pdf;type=application/pdf' \
  http://127.0.0.1:8000/v1/documents
```

Uma aceitação retorna HTTP `202 Accepted` e um JSON semelhante a este formato:

```json
{
  "document_id": "UUID gerado pelo serviço",
  "status": "STORED",
  "correlation_id": "UUID da requisição",
  "received_at": "data e hora UTC"
}
```

Use os valores `document_id` e `correlation_id` retornados pela sua chamada.
`curl --include` também exibe o cabeçalho `X-Correlation-ID`. Para consultar
metadados e acompanhar o estado de publicação, substitua `DOCUMENT_ID` pelo
UUID recebido:

```bash
curl --fail --show-error \
  http://127.0.0.1:8000/v1/documents/DOCUMENT_ID
```

A consulta retorna metadados, tamanho, checksum e estado, sem devolver o
arquivo nem a localização ou URL do armazenamento. O estado pode estar em
`STORED` enquanto o evento aguarda publicação; após confirmação do RabbitMQ,
pode aparecer como `PUBLISHED`. A API também expõe o contrato OpenAPI em
`http://127.0.0.1:8000/docs`.

O contrato aceita um PDF, PNG ou JPEG por requisição. A assinatura do arquivo
é validada além do nome e do tipo informado. O limite padrão do arquivo é
10 MiB; o excesso retorna `413`, e um tipo não aceito retorna `415`.

## O que acontece depois

1. A API valida o tipo, tamanho e assinatura do arquivo recebido.
2. O original é gravado privadamente no Azurite, com uma chave gerada pelo
   serviço.
3. Metadados do documento e o evento pendente são persistidos no PostgreSQL;
   o registro do documento e da outbox ocorre na mesma transação.
4. A API retorna `202` depois de concluir armazenamento e persistência. Essa
   confirmação não aguarda o RabbitMQ nem um consumidor de negócio.
5. O worker lê a outbox e publica `document.received.v1` no RabbitMQ. Depois
   da confirmação do broker, o estado consultável passa para `PUBLISHED`.

A publicação tem entrega pelo menos uma vez. Uma falha durante a confirmação
pode resultar em repetição; qualquer consumidor futuro deve tolerar o mesmo
evento mais de uma vez por meio de processamento idempotente. O tutorial não
inicia Processing, Triage ou Registry.

## Verificações locais

Veja saúde e portas publicadas:

```bash
docker compose ps
```

Veja os logs da API, do worker ou do Azurite:

```bash
docker compose logs --tail=100 api
docker compose logs --tail=100 worker
docker compose logs --tail=100 azurite
```

O RabbitMQ inclui a interface de gerenciamento na porta local `15672`:
`http://127.0.0.1:15672`. Para entrar, use os valores locais de
`RABBITMQ_USER` e `RABBITMQ_PASSWORD` definidos no `.env`. A interface permite
observar o estado do broker e da fila `docpipe.document.received.v1`. A porta
AMQP para conexões locais é `5672`. O Compose não inclui uma interface web
própria para o Azurite; seu health check e seus logs podem ser consultados
pelos comandos acima.

## Solução de problemas

### Porta já está em uso

O Compose publica por padrão API em `8000`, métricas/saúde do worker em `9001`,
PostgreSQL em `5432`, AMQP em `5672`, gerenciamento RabbitMQ em `15672` e Blob
do Azurite em `10000`. Confira containers e portas com:

```bash
docker compose ps
docker ps
```

Se necessário, altere a variável de porta correspondente no `.env` e recrie
os containers do projeto com `docker compose up -d`. As portas padrão ficam
vinculadas a loopback.

### Container não saudável ou serviço ainda inicializando

Consulte o estado e os logs do container afetado:

```bash
docker compose ps
docker compose logs --tail=150 postgres
docker compose logs --tail=150 azurite
docker compose logs --tail=150 rabbitmq
docker compose logs --tail=150 api
docker compose logs --tail=150 worker
```

Aguarde a inicialização e confira novamente a rota de readiness correspondente.
Se a preparação falhou, veja os logs e execute de novo o comando do serviço
`setup` antes de iniciar ou reiniciar API e worker.

### Upload rejeitado

Confira se o arquivo é PDF, PNG ou JPEG válido e se não excede o limite
configurado. O serviço responde `415` para tipo não aceito e `413` para
arquivo ou corpo acima do limite. Consulte o corpo da resposta HTTP e os logs
da API; não envie documentos reais para diagnóstico.

### Docker Compose não conecta ao daemon

Confira a disponibilidade do Docker Engine:

```bash
docker info
docker compose ps
```

Inicie o Docker Engine e repita os comandos quando o daemon estiver acessível.

## Encerramento e dados persistidos

Para parar os containers mantendo os dados locais, use:

```bash
docker compose stop
```

Para removê-los preservando os volumes deste projeto:

```bash
docker compose down --remove-orphans
```

Os volumes guardam dados do PostgreSQL, Azurite e RabbitMQ e são mantidos
pelos comandos acima. `docker compose down --volumes` remove também esses
volumes e apaga os dados persistidos do projeto. Use essa opção somente se
quiser conscientemente descartar todos os dados locais do Ingestion.

## Limites da versão

A `v1.0.0` descrita aqui é local e portátil: usa Docker Compose, PostgreSQL,
Azurite e RabbitMQ, sem cloud provider. O PostgreSQL local não usa TLS e sua
porta é publicada somente em loopback por padrão. Esta configuração não
representa uma configuração de produção; cloud provider e TLS de produção
pertencem a uma evolução futura.

O DocPipe tem quatro microsserviços independentes. Este repositório executa
somente Ingestion; Processing, Triage e Registry mantêm repositórios e
responsabilidades próprios e não fazem parte deste ambiente local.
