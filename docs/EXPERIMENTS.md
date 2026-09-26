# Experimentos locais da Etapa 9

Este laboratório mede somente o DocPipe Ingestion. `202` confirma arquivo,
metadados e evento outbox persistidos; `PUBLISHED` confirma publicação do
evento inicial no RabbitMQ. Não há consumidor de negócio, OCR ou processamento
dos futuros microserviços. Os resultados descrevem este notebook e esta
configuração, sem extrapolação automática para produção.

## Preparação e limites

Use Docker Compose local, Python 3.14.4 e uv. A primeira execução precisa baixar
as imagens fixadas e construir as imagens da aplicação e do Locust. Nenhuma
porta de dependência ou da API é publicada no host. Cada execução recebe um
`run_id`, projeto Compose, rede, volumes e fila próprios. O script aceita apenas
contexto Docker com socket Unix local e confere o rótulo do projeto antes de
parar um container. Não aponte este laboratório para um Docker remoto.

```bash
uv sync --locked --group dev
uv run --locked python -m experiments.lab preflight
uv run --locked python -m experiments.lab run smoke
```

O preflight exige quatro CPUs lógicas, pelo menos 4,5 GiB disponíveis para o
host e para o daemon Docker e 5 GiB livres em disco. Ele verifica o contexto
antes de iniciar serviços. Os limites Compose somam até 3 CPUs e 2.944 MiB:
PostgreSQL 0,4 CPU/512 MiB; RabbitMQ 0,3/512; Azurite 0,3/384; API
1,0/512; worker 0,5/384; Locust 0,4/512; coletor 0,1/128. Nas comparações,
o orçamento total de API ou worker é dividido entre duas instâncias. Um smoke
deve confirmar que os limites por processo são suficientes no notebook real.

A execução para a geração diante de memória disponível abaixo de 1,5 GiB por
10 segundos, CPU do host acima de 90% ou do Locust próxima de seu limite por
30 segundos, aumento de swap acima de 128 MiB por 30 segundos, menos de 2 GiB
livres em disco, mais de 2 GiB em artefatos, backlog acima de 500 eventos,
2.000 POSTs ou dez erros HTTP inesperados consecutivos. O script preserva os
volumes e registra a interrupção. Além dos limites, o operador deve acompanhar
temperatura, responsividade do notebook e aplicações concorrentes.

Os seis documentos são criados por `experiments/fixtures.py`: dois PDFs, dois
PNGs e dois JPEGs válidos, cada um menor que 64 KiB. O JPEG está incorporado
como base64 de um padrão sintético de 2 × 2 pixels. Seu segundo arquivo reutiliza
os mesmos bytes com nome diferente. Cada POST ganha nome contendo o `run_id`
e uma sequência; o contrato atual não oferece `Idempotency-Key` nem deduplica
por checksum. O manifesto registra os hashes e tamanhos efetivos. Locust faz um
POST e, após `202`, um GET dos metadados, sem repetir automaticamente o POST
após timeout.

## Perfis de carga

Os padrões estão em `experiments/scenarios.json`. Os parâmetros seguros podem
ser ajustados pelos argumentos `--users`, `--spawn-rate`, `--wait-seconds`,
`--warmup-seconds`, `--measure-seconds` e `--max-posts`. A carga progressiva usa
os patamares definidos no JSON. O controlador rejeita valores acima de oito
usuários, dois usuários novos por segundo, 180 segundos de medição, 2.000 POSTs
ou espera inferior a dois segundos entre tarefas.

| Perfil | Usuários | Aquecimento | Medição | Repetições sugeridas |
| --- | ---: | ---: | ---: | ---: |
| `smoke` | 1 | 10 s | 50 s | 1 |
| `baseline` | 2 | 30 s | 180 s | 3 |
| `progressive` | 2, 4, 8 | 30 s por patamar | 120 s por patamar | 3 |
| `api-scale` | 2 | 30 s | 180 s | 3 pares |
| `worker-scale` | 2 para preparar 100 documentos | não incluído na medição | até 180 s de drenagem | 3 pares |

```bash
uv run --locked python -m experiments.lab run baseline
uv run --locked python -m experiments.lab run progressive
uv run --locked python -m experiments.lab run api-scale --apis 1
uv run --locked python -m experiments.lab run api-scale --apis 2
uv run --locked python -m experiments.lab run worker-scale --workers 1
uv run --locked python -m experiments.lab run worker-scale --workers 2
```

Cada comando executa uma repetição em um projeto novo. Para três repetições,
execute o comando três vezes, alternando a ordem dos pares de escala. Avance à
comparação somente após revisar o baseline, a saúde, memória, CPU, swap e
backlog. O Locust alterna os POSTs entre `api` e `api2` quando há duas APIs e
consulta cada documento pela outra instância. Isso verifica distribuição e
estado compartilhado sem introduzir balanceador. Duas APIs usam PostgreSQL e
Azurite; SQLite e storage local permanecem restritos ao modo simples. Dois
workers disputam eventos com `FOR UPDATE SKIP LOCKED`; o relatório registra
tempo de drenagem, tentativas e eventuais duplicatas. A comparação não exige
ganho de desempenho. Se o notebook não suportar as variantes, registre o
adiamento para o futuro repositório integrador.

Usuários concorrentes são usuários virtuais ativos, não total de requisições.
O total é a soma acumulada de POSTs e GETs. RPS é essa soma por segundo;
documentos aceitos por segundo contam apenas POSTs `202` na janela medida.
O tempo de resposta e os percentis do CSV Locust pertencem ao HTTP. O worker
é avaliado pela drenagem da outbox, em relatório separado.

## Falhas isoladas

Os cenários abaixo começam com 30 segundos saudáveis, param somente o serviço
indicado por 30 segundos e observam a recuperação por até 180 segundos.
Execute um cenário por vez, primeiro como ensaio e depois em duas repetições
registradas. `--failure-seconds` permite uma janela menor; o máximo é 30 s.

```bash
uv run --locked python -m experiments.lab run rabbitmq
uv run --locked python -m experiments.lab run azurite
uv run --locked python -m experiments.lab run postgres
uv run --locked python -m experiments.lab run worker
uv run --locked python -m experiments.lab run api
```

O controlador verifica a saúde de PostgreSQL, RabbitMQ, Azurite, API e worker
antes de introduzir a falha e confirma o rótulo Compose do alvo. Ele registra
início, parada efetiva, restauração da saúde e fase de recuperação em
`timeline.jsonl`. A falha do RabbitMQ deixa a API apta a aceitar pela outbox.
O worker atual não reconecta ao canal após perda da conexão: o controlador o
recria depois de restaurar o broker. Somente nesse cenário, o laboratório usa
dez tentativas máximas, registradas no manifesto; os demais perfis preservam
o padrão de cinco. Eventos esgotados não são reativados automaticamente.

Na falha do Azurite, uploads afetados podem responder `503` ou ter resultado
incerto por timeout; o GET de metadados usa o banco. Na falha do PostgreSQL,
POST/GET afetados podem responder `503`, e uploads concluídos antes de um
commit falho podem deixar objetos órfãos. O worker também pode encerrar e é
recriado após o banco voltar. Parar somente o worker deve acumular eventos
pendentes sem impedir `202`. Reiniciar somente a API não perde documentos já
aceitos. Erros esperados são classificados apenas na janela da falha da
dependência correspondente. `500`, resposta fora do contrato ou falha após a
recuperação são desvios.

Publisher confirms e o registro no banco deixam uma janela de duplicidade:
uma confirmação seguida de falha no commit pode gerar outra publicação com o
mesmo `event_id`. A entrega é pelo menos uma vez. Um timeout do cliente não
comprova se o POST foi persistido; consulte o manifesto, o nome sintético e a
auditoria antes de repetir qualquer operação.

## Evidências e interpretação

O comando imprime o caminho no início. Resultados ficam em
`artifacts/experiments/<run_id>/`, ignorados pelo Git e excluídos da imagem.
Cada pasta contém `manifest.json` com commit, estado de alterações locais,
versões, parâmetros, recursos iniciais, nomes, tamanhos e SHA-256 dos arquivos;
`timeline.jsonl`; `outcomes.jsonl` com respostas e fases; CSV/HTML do Locust;
`resources.jsonl` com `docker stats`, CPU, memória e swap do host;
`service-samples.jsonl` com métricas existentes e backlog consultado ao banco;
logs da execução, `audit.json` e `summary.json` quando disponíveis. Falhas
anteriores ao início dos containers geram `blocked.json` e um resumo parcial.

`summary.json` distingue aceitações HTTP, erros esperados e inesperados, dados
persistidos, pendentes e integridade de objetos. Os percentis p50/p95/p99 e
RPS vêm do Locust e são exibidos somente quando o CSV correspondente existe.
Os gauges `/metrics` da API podem ficar desatualizados durante falha do banco;
o snapshot do banco marca explicitamente `database_unavailable`. Cada API e
worker tem registry próprio. Não some o backlog visto por duas APIs nem
interprete `PUBLISHED` como processamento completo do documento.

`published_at` é gravado com o horário do início da tentativa confirmada e
não mede exatamente o instante do publisher confirm. O resumo identifica como
**estimativa** a diferença entre esse horário e o registro do `202` pelo
Locust; a diferença pode ser negativa quando o worker publica antes de o
cliente receber a resposta. O tempo de recuperação do backlog usa snapshots
de cinco em cinco segundos e aparece somente quando houve backlog durante a
falha. Sem backend de tracing, os logs mantêm IDs de
correlação e trace/span quando presentes; exportação OTLP continua opcional.

Após a publicação terminar, pode-se restaurar o projeto preservado e auditar
os envelopes na fila exclusiva:

```bash
uv run --locked python -m experiments.lab recover RUN_ID
uv run --locked python -m experiments.lab audit RUN_ID
uv run --locked python -m experiments.lab audit RUN_ID --drain
uv run --locked python -m experiments.lab stop RUN_ID
```

`recover` reinicia os serviços identificados e executa uma auditoria sem drenar
a fila. `--drain` valida os eventos e confirma
sua remoção da fila **somente do projeto indicado**; use depois de preservar
contagem e métricas, pois altera a fila. O relatório inclui número de mensagens
e IDs de evento repetidos, sem afirmar processamento de outro serviço. Os
relatórios não contêm `.env`, connection strings, payloads, binários nem
segredos. O laboratório usa apenas credenciais sintéticas locais, presentes na
composição, nunca valores reais.

## Recuperação e limpeza

Ctrl+C ou SIGTERM faz o controlador parar o Locust, restaurar o serviço cuja
falha estava em curso, coletar os logs e parar os containers do projeto.
Volumes e resultados são preservados. Após encerramento abrupto, queda de
energia ou falha da restauração automática, identifique `RUN_ID` no caminho
impresso ou em `artifacts/experiments/` e execute:

```bash
uv run --locked python -m experiments.lab recover RUN_ID
uv run --locked python -m experiments.lab audit RUN_ID
uv run --locked python -m experiments.lab stop RUN_ID
```

`recover` só aceita manifesto de laboratório e verifica os containers antes
de restaurar PostgreSQL, RabbitMQ, Azurite, API e worker. Ele não reinicia a
carga. Verifique `pending`, `exhausted`, integridade dos blobs e mensagens na
fila antes de encerrar. Se houver evento esgotado, preserve a evidência e
investigue a causa; este estágio não possui comando de reenvio controlado.

Não há limpeza automática de volumes ou dados. Para examinar uma execução
descartável **após arquivar suas evidências**, substitua `RUN_ID` pelo valor do
manifesto e confira o rótulo de cada resultado:

```bash
uv run --locked python -m experiments.lab stop RUN_ID
docker ps -a --filter label=com.docker.compose.project=docpipe-RUN_ID
docker volume ls --filter label=com.docker.compose.project=docpipe-RUN_ID
```

Remova somente os containers e volumes concretos conferidos nessa lista, após
revisar `audit.json` e preservar os relatórios. A remoção de volumes é sempre
uma decisão manual posterior. Não use `docker system prune`, purga de filas
compartilhadas nem os testes de integração opt-in contra estes volumes, pois
alguns testes limpam tabelas e filas.

O gerador, a aplicação e as dependências disputam CPU, RAM, I/O e rede no
mesmo notebook. Percentis e throughput podem variar com cache, temperatura,
swap, processos externos e sistema de arquivos. Registre essas condições e
compare somente execuções com orçamento e massa equivalentes. A Etapa 9 só
estará completamente validada após executar os cenários e revisar as
evidências reais; ter os scripts e a CI verdes não substitui essa execução.
