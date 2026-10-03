# Auditoria 10a da candidata local `v1.0.0`

## Escopo, revisão e decisão

- Revisão auditada: `7e48d5fc2b1b01a4cec5246f71ab615f01b85f76`
  (merge da [PR #16](https://github.com/RogerioCampos07/docpipe-ingestion/pull/16)).
- Branch de trabalho: `chore/phase-10a-release-audit`; árvore limpa no início
  da auditoria. `HEAD` e a referência local `origin/main` coincidiam. Não foi
  feito `fetch`, checkout, build, teste, migration ou início de containers.
- Ambiente observado: Python `3.14.4`, uv `0.9.26`, Docker `29.7.2`, Compose
  `v5.5.0`; 3,3 GiB de RAM visíveis, 2,7 GiB disponíveis, sem swap; 4,2 GiB
  livres no filesystem de 76 GiB. A memória observada é menor que os 8 GiB
  nominais do notebook. Nenhuma stack foi criada nesta auditoria.
- Critérios: `docs/REQUIREMENTS.md` (RF-001–008, RNF-001–009, CTs e definição
  de pronto), `docs/DESIGN.md`, `docs/PLAN.md`, `README.md`, `docs/CI.md`,
  `docs/OBSERVABILITY.md`, `docs/EXPERIMENTS.md` e `AGENTS.md`.
- **Conclusão da 10a:** auditoria registrada, com pendências para a 10b.
  **Candidata:** ainda bloqueada para aceite da `v1.0.0` pelos itens B1–B6.
  A classificação não equivale a publicar ou fechar a release.

A entrega avaliada é local: Compose oficial, PostgreSQL exclusivo do Ingestion,
Azurite, RabbitMQ, API e worker separados. O Ingestion não requer Processing.
Azure pertence à `v1.1.0`; Kubernetes, observabilidade central e experimentos
acadêmicos não são critérios desta candidata. O `202` confirma blob e commit
de metadados/outbox; `PUBLISHED` confirma o broker, não um consumidor. Blob,
banco e broker não formam transação distribuída. A entrega é pelo menos uma vez.

## Origem e alcance das evidências

| ID | Origem e revisão | Resultado verificável | Limite |
| --- | --- | --- | --- |
| G | [Actions push `36954608701`](https://github.com/RogerioCampos07/docpipe-ingestion/actions/runs/36954608701), SHA auditado | `ci-quality`, `ci-tests` e `ci-image` concluídos com `success`. Os passos de migrations/setup, teste HTTP `packaged`, verificadores JUnit e cobertura tiveram `success`. | O artefato de `ci-tests` foi listado, mas seu download retornou HTTP 403; `ci-image` publica artefato apenas se falhar. Contagens e percentual exatos desse run não foram obtidos. |
| P | [Actions PR `36954329033`](https://github.com/RogerioCampos07/docpipe-ingestion/actions/runs/36954329033), `9dcdeab38c57dc371b5e5aaca20efa5b6942729a` | Os mesmos três jobs concluíram com `success`. | Revisão da PR, distinta do SHA do merge. |
| U | JUnit local da Parte 1, associado pelo histórico a `72a9d4e41695e195434649060a4babc9678892f9` | 176 testes sem serviços; zero falhas, erros e skips; sete excluídos pela seleção. | XML em `/tmp/docpipe-etapa9-part1-20261002/unit.xml` não contém SHA. |
| I | JUnit local da Parte 1, mesma revisão histórica | Seis integrações reais; zero falhas, erros e skips; 177 excluídos. | XML em `/tmp/docpipe-etapa9-part1-20261002/integration.xml` não contém SHA. |
| K | JUnit local da Parte 2, imagem construída do código `72a9d4e` e harness posteriormente corrigido em `9dcdeab` | Última tentativa: um `packaged` aprovado, zero falhas, erros e skips; 182 excluídos. As duas tentativas anteriores falharam no harness e foram preservadas. | XML em `/tmp/docpipe-etapa9-part2-20261002/retry2/packaged-compose.xml` não contém SHA. |
| C | Inspeção estática da árvore auditada | Implementação, testes e configuração listados abaixo. | Existência de código ou teste não substitui execução. |

O build local K registrou a imagem
`sha256:2ab002166e2978f10e2a18deb86ed81afdd2cc9e196fb0bd8e5b1297bf563de0`.
`git diff --quiet 9dcdeab..7e48d5f` confirmou árvores idênticas. Entre
`72a9d4e` e a árvore auditada mudaram somente `tests/conftest.py` e
`tests/integration/test_packaged_compose.py`: a fixture preserva a idade de
uploads incompletos quando o teste `packaged` está habilitado, e o harness
acompanha mensagens já recebidas mas não confirmadas. Assim, U/I sustentam o
código da aplicação atual e K sustenta o harness atual, com a ressalva de que
os XML locais não registram o commit. G comprova execução posterior da árvore
do merge pelo GitHub e é a evidência principal da revisão auditada.

O workflow `ci-tests` acumula cobertura de linhas e branches entre testes sem
serviços e integrações reais; `packaged` é separado. O relatório local U+I
registrou **88%**, sem piso percentual configurado em `pyproject.toml` ou no
workflow. Esse número não é atribuído ao run G, cujo percentual não foi
recuperado. O verificador JUnit rejeita relatório ausente/vazio, erro, falha,
skip e módulos obrigatórios ausentes. G comprova que seus passos passaram;
não foi executado novamente nesta 10a.

Nesta auditoria, a API pública do GitHub confirmou jobs e passos do run G;
`gh auth status` encontrou token inválido, e as consultas públicas a branch
protection/arquivo de artefato retornaram 401/403. A revisão de links locais
dos documentos não encontrou alvo ausente. `uv run --locked --no-sync typos`
e `git diff --check` passaram. `typos` exclui Markdown pela configuração
existente, portanto a redação foi revista separadamente. Não foram executados
pytest, build, migrations ou novos containers na 10a.

## Matriz de conformidade

`Comprovado` exige implementação e resultado pertinente para esta árvore.
`Parcial` indica subcritério ou cenário sem prova suficiente. `Não comprovado`
indica ausência de resultado necessário, sem concluir que a implementação
falha. `Não aplicável` exige exclusão documental explícita. As referências
G/U/I/K/C acima indicam a revisão de cada resultado; os caminhos abaixo
identificam implementação e teste, não um teste novo da 10a. Os caminhos
abreviados de código e teste são relativos a `src/docpipe_ingestion/` e
`tests/`; `migrations/` e arquivos de configuração ficam na raiz.

| Critério | Implementação | Teste/evidência e revisão | Estado, fundamento e próximo passo |
| --- | --- | --- | --- |
| RF-001 — entrada e `202` | `api/routes/documents.py`, `api/schemas/documents.py`, `application/ingest_document.py` | `tests/api/test_documents.py` U/G; `test_packaged_compose.py` K/G | **Comprovado:** três formatos, UUID e resposta após persistência. |
| RF-002 — validação | `application/file_validation.py`, `api/exception_handlers.py` | `test_file_validation.py`, `test_documents.py` U/G; rejeições K/G | **Parcial:** validação do arquivo é testada, mas não há limite explícito para o corpo multipart antes do parse; B1. |
| RF-003 — storage privado | `infrastructure/storage/azure_blob.py`, `storage/local.py`, `storage/keys.py` | `test_azurite.py`, `test_storage.py` I/G; conteúdo e privacidade K/G; falha local U/G | **Parcial:** caminho feliz real; falha de escrita do Azurite não foi comprovada como tal; B2. |
| RF-004 — metadados e migrations | `database/models.py`, `unit_of_work.py`, `migrations/versions/` | `test_postgresql.py` I/G; setup e DB K/G | **Comprovado:** schema em PostgreSQL, campos e rollback conjunto verificados. Reversão PostgreSQL não foi provada, mas não há nova migration nesta revisão. |
| RF-005 — SHA-256 | `file_validation.py`, `azure_blob.py` | `test_file_validation.py` U/G; blob, metadados e evento K/G | **Comprovado:** hashing em chunks e igualdade com bytes armazenados. |
| RF-006 — evento/outbox | `application/events.py`, `publish_outbox.py`, `messaging/rabbitmq.py` | `test_events.py`, `test_publish_outbox.py` U/G; `test_rabbitmq.py` I/G; K/G | **Comprovado:** transação documento/outbox, confirm, mensagem persistente, `mandatory`, retry/backoff e publicação pelo worker. O cenário especial de commit incerto está em CT-016. |
| RF-007 — consulta | `api/routes/documents.py`, `get_document.py` | `test_documents.py` U/G; GET K/G | **Comprovado:** `200`/`404` e projeção sem binário, URL ou credencial. |
| RF-008 — saúde/métricas | `api/routes/health.py`, `infrastructure/health.py`, `worker_server.py` | `test_health.py`, `test_worker_observability.py` U/G; saúde K/G | **Comprovado:** liveness, readiness funcional, métricas sem backend obrigatório e resposta sanitizada; indisponibilidade real de DB/Azurite segue CT-013. |
| RNF-001 — streaming/recursos | `file_validation.py`, `azure_blob.py`, API multipart | leitura limitada U/G; fluxo K/G | **Parcial:** streaming do caso de uso é comprovado; parse do corpo antecede o limite do arquivo e pode consumir disco temporário; B1. Campanhas de desempenho são não aplicáveis. |
| RNF-002 — separação/coordenação | Compose, `application/ports.py`, repositório SQL | `test_postgresql.py` I/G; API/worker K/G | **Comprovado:** processos separados e `SKIP LOCKED`; não exige comparação de réplicas. |
| RNF-003 — confiabilidade | `publish_outbox.py`, `requeue_outbox_event.py`, `reconciliation.py` | U/I/K/G | **Parcial:** falha do broker, esgotamento, reenvio, retomada e órfão têm prova; CT-013, CT-015 e CT-016 ainda limitam o conjunto; B2–B4. |
| RNF-004 — segurança/LGPD | settings, Compose, Dockerfile, handlers, logging | revisão estática C; testes de privacidade U/G; usuário da imagem K/G | **Parcial:** nenhuma credencial real apareceu na busca dirigida; B1 e B5 impedem fechar a revisão de recursos/dependências. TLS de produção e política para dados pessoais reais são condições de uso fora da operação local sintética. |
| RNF-005 — observabilidade | `api/correlation.py`, `infrastructure/observability/`, `diagnostics.py` | testes de logs, métricas e traces U/G; correlação K/G | **Comprovado:** instrumentação do serviço e exportação opcional, sem stack central. |
| RNF-006 — portabilidade | `application/ports.py`, adaptadores, Compose | contratos U/I/G; aplicação empacotada K/G | **Comprovado:** execução sem cloud e sem outro serviço DocPipe; compatibilidade com Azure real é evolução `v1.1.0`. |
| RNF-007 — manutenção/versão | `pyproject.toml`, migrations, rotas/evento | `ci-quality` G; OpenAPI U/G; migration PostgreSQL I/G | **Parcial:** qualidade passa, mas pacote/lock `0.1.0` e OpenAPI `1.0.0` exigem decisão/alinhamento na 10b; B6. |
| RNF-008 — CI | `.github/workflows/ci.yml`, `verify_pytest_junit.py` | jobs e verificadores G; PR P | **Comprovado:** três checks, opt-ins, cobertura, JUnit, imagem e serviços reais passaram para o SHA auditado. Proteção efetiva da branch não foi acessível; L3. |
| RNF-009 — autonomia | Compose próprio, banco/migrations/CI próprios, contrato HTTP/evento | inspeção C; K/G sem Processing, broker sem consumidor | **Comprovado:** fluxo próprio sem checkout, banco ou processo de outro microserviço. |
| CT-001 — PDF | API/storage/DB/outbox | `packaged` K/G | **Comprovado:** `202`, blob, DB e outbox. |
| CT-002 — PNG/JPEG | mesmos módulos | `packaged` K/G | **Comprovado:** ambos percorrem fluxo e mensagem. |
| CT-003 — vazio | `file_validation.py` | unitário U/G e HTTP K/G | **Comprovado:** rejeitado. |
| CT-004 — tipo inválido | `file_validation.py` | unitário U/G e HTTP K/G | **Comprovado:** `415`, sem novo evento/blob completo. |
| CT-005 — excede limite | `file_validation.py`, handlers | limite unitário U/G; OpenAPI U/G | **Parcial:** `413` está mapeado, mas não foi exercitado por HTTP na imagem; corpo sem limite prévio, B1. |
| CT-006 — falha de storage | `azure_blob.py`, handlers | falha local simulada U/G; Azurite saudável I/K/G | **Parcial:** falta falha real do Azurite sem falso sucesso e recuperação; B2. |
| CT-006A — nome malicioso | `sanitize_original_name`, chaves opacas | testes de nomes/local U/G; chave Azurite K/G | **Comprovado:** caminho do cliente não vira chave; adaptador local contém escape. |
| CT-007 — broker indisponível | outbox e worker | falha do broker K/G | **Comprovado:** API aceita e evento permanece pendente. |
| CT-008 — worker reiniciado | `outbox_worker.py` | recuperação K/G | **Comprovado:** canal perdido produz saída não zero, reinício explícito publica pendentes. |
| CT-009 — ausente | rota GET | API U/G | **Comprovado:** `404`. |
| CT-010/011 — carga/escala | laboratório histórico | exclusão explícita em `REQUIREMENTS.md` | **Não aplicável:** retirados do aceite local; não excluir testes funcionais. |
| CT-012 — reinício API/worker | Compose e volumes | recriação K/G | **Comprovado:** dados aceitos consultáveis. |
| CT-013 — DB/Azurite indisponível | health, erros HTTP, reconciliação | mocks API U/G; trigger DB K/G | **Parcial:** trigger simula falha de persistência, não indisponibilidade temporária real de PostgreSQL ou Azurite com recuperação; B2. |
| CT-014 — bytes repetidos | IDs opacos e SHA | `packaged` K/G | **Comprovado:** IDs distintos e checksum igual; sem deduplicação. |
| CT-015 — reenvio | `requeue_outbox_event.py`, repositório | U/G; reenvio empacotado K/G | **Parcial:** IDs/payload, publicação e log são testados; corrida real reenvio/publicação em PostgreSQL não é exercitada; B3. |
| CT-016 — confirm seguido de commit falho | publisher e UoW | `test_uncommitted_confirmation_can_be_published_again` U/G | **Parcial:** o teste publica duas vezes com dublês, sem falha real de commit após confirm; B4. |
| CT-017 — dependências e volumes | Compose | recriação K/G | **Comprovado:** DB, blob, mensagem durável e pendente sobrevivem à recriação. |

### Definição de pronto da versão

| Critério de `REQUIREMENTS.md`, seção 5 | Estado e razão |
| --- | --- |
| Instalação, migrations e Compose reproduzíveis | **Comprovado** em G e K; comandos documentados em `README.md`/`docs/CI.md`. |
| Serviços reais separados, sem Processing | **Comprovado** em G/K. |
| Blob privado, SHA, metadados, outbox e mensagem conjunta | **Comprovado** em G/K. |
| Contratos, erros, duplicidade, reenvio, órfãos e reinícios | **Parcial** por CT-005/006/013/015/016; B1–B4. |
| Requisitos associados a evidências da revisão e checks GitHub | **Parcial**: G pertence ao SHA correto, mas os critérios parciais acima carecem de prova. |
| Imagem sem root, dependências verificadas, sem segredos reais | **Parcial**: UID confirmado; inventário de vulnerabilidades e imagem incompletos, B5. |
| `ci-image` usa imagem e HTTP sem mounts do checkout | **Comprovado** por G e assertions de K; checkout executa só o harness. |
| Documentação, versão, limitações e decisão de aceite | **Parcial**: relatório e correções documentais existem na 10a; alinhamento da versão/aceite é 10b, B6. |

## Revisão de segurança, CI e operação

- **Segredos:** somente `.env.example` foi encontrado entre os arquivos `.env`
  rastreados; `.env` é ignorado e `.dockerignore` o exclui da imagem. A busca
  dirigida por padrões de chave/token/senha apontou apenas `.env.example`,
  com credenciais declaradas como locais no README. Isso não constitui prova
  exaustiva de ausência de segredos, inclusive no histórico ou em artefatos.
- **Portas/privacidade:** Compose publica API, worker, PostgreSQL, Azurite e
  RabbitMQ em `127.0.0.1` por default. Blobs são criados com acesso privado;
  as respostas públicas não incluem bytes ou credenciais. Não usar os valores
  de exemplo em ambiente compartilhado ou de produção.
- **Entrada/recursos:** assinatura, tipo, extensão, nome, chave opaca e limite
  de arquivo têm validação e testes. `request.form()` executa antes de
  `ValidatedFileStream`; não foi localizado limite explícito do corpo HTTP ou
  de espaço temporário no Compose. O risco é consumo de disco antes do `413`.
- **Logs/erros:** handlers retornam códigos e mensagens estáveis; os testes
  inspecionam logs/métricas sem conteúdo nem labels de alta cardinalidade. A
  busca estática não substitui ensaio de caminhos excepcionais completos.
- **Imagem/permissões:** Dockerfile fixa `USER 10001:10001`, usa lockfile,
  copia pacote/migrations e exclui dev deps; K verifica UID, image ID e zero
  mounts de aplicação. Os volumes duráveis pertencem aos serviços de dados.
  Imagens locais antigas e um `docpipe-control-plane` já ativo foram apenas
  listados; nenhum desses recursos foi modificado ou removido.
- **Dependências:** `uv.lock` contém 50 pacotes na cadeia de execução, 15
  diretos. Em 02/10/2026, consultas públicas a GitHub Global Security
  Advisories com `ecosystem=pip` e `affects=nome@versão` obtiveram resposta
  para 45 pacotes, sem alertas retornados para essas versões. A sintaxe foi
  conferida contra uma versão historicamente vulnerável. O limite da API
  interrompeu cinco consultas: `typing-extensions`, `typing-inspection`,
  `tzdata`, `urllib3` e `wrapt`. `uvicorn` foi consultado separadamente antes
  do limite. OSV querybatch retornou HTTP 403.
  As imagens Python, uv, PostgreSQL, RabbitMQ e Azurite têm tags declaradas,
  mas não houve inventário de seus pacotes/digests ou advisories. **Não há
  conclusão de ausência de vulnerabilidades.**
- **CI:** workflow padrão concede `contents: read`, usa ações pinadas por SHA,
  timeouts e concorrência; jobs têm projetos isolados e limpeza com escopo.
  O workflow manual do laboratório é histórico e não integra os três checks.
  `ci-tests` sobe infraestrutura só após testes sem serviços, publica JUnit e
  cobertura sempre e limpa volumes do projeto do run. `ci-image` publica
  diagnóstico apenas em falha; o sucesso é verificável pelo run G, sem JUnit
  baixável via acesso público. API pública retornou HTTP 401 ao consultar
  proteção da `main` e 403 ao baixar o artefato `ci-tests`.
- **Operação:** README e `docs/CI.md` trazem setup controlado, health,
  reenvio, reconciliação somente leitura, reinício explícito do worker e
  encerramento que preserva volumes. Os testes `packaged` recriam containers
  preservando os dados. A documentação de política para dados pessoais reais
  continua sendo condição anterior a esse uso, não prova da operação local.

## Achados e trabalho priorizado para a 10b

`P1` indica critério obrigatório ou evidência essencial que impede o aceite;
`P2` indica melhoria adiável ou acesso complementar. Nenhum achado abaixo é
apresentado como falha de teste que não ocorreu.

| ID | Prioridade e tipo | Local, impacto e ação verificável |
| --- | --- | --- |
| B1 | P1 — defeito/limite | `api/dependencies.py` chama `request.form()` antes do limite em `application/file_validation.py`; RNF-001, RF-002, CT-005 e `DESIGN.md` §12 exigem recursos limitados. Estabelecer limite de corpo/uso temporário antes do parse, preservando streaming; provar `413`, ausência de aceitação parcial e uso limitado de recursos por HTTP real. |
| B2 | P1 — evidência funcional | CT-006 e CT-013: falha local simulada e trigger DB não exercitam indisponibilidade temporária real de Azurite/PostgreSQL. Em projeto descartável, interromper uma dependência por vez, observar HTTP/readiness, preservar registros aceitos, restaurar e verificar consulta/publicação/reconciliação. Usar a imagem entregue se a correção a alterar. |
| B3 | P1 — evidência de concorrência | CT-015: reenvio condicional está em `database/repositories.py`; testes atuais cobrem o caminho normal e evento publicado, mas não uma corrida PostgreSQL com worker ativo. Provar que o resultado conserva ID/payload e não reativa evento publicado; corrigir somente se a corrida revelar defeito. |
| B4 | P1 — evidência de duplicação permitida | CT-016: `test_uncommitted_confirmation_can_be_published_again` usa dublê e publica duas vezes sem falha de commit. Em infraestrutura isolada, injetar falha após confirm e antes do commit, reiniciar/reprocessar e verificar eventual repetição com o mesmo `event_id`, sem outro documento. Não exigir entrega exatamente uma vez. |
| B5 | P1 — revisão de dependências incompleta | `uv.lock`, Dockerfile e Compose: cinco pacotes de execução e as imagens ficaram sem avaliação de advisories aplicáveis. Completar consulta atualizada, registrar fonte/data/versões/digests e triagem; corrigir somente vulnerabilidade aplicável encontrada. A indisponibilidade das fontes é lacuna de evidência, não vulnerabilidade confirmada. |
| B6 | P1 — preparação da candidata | `pyproject.toml` e `uv.lock` declaram `0.1.0`; `api/app.py` declara OpenAPI `1.0.0`. Definir e alinhar versão e documentação na 10b, atualizar lockfile pela ferramenta, preservar `/v1` e `document.received.v1` e reexecutar checks pertinentes da revisão resultante. |
| L1 | P2 — durabilidade da evidência | JUnit locais não carregam SHA; artefatos do GitHub expiram em sete dias e `ci-image` só publica em falha. Preservar resumo sanitizado e, se necessário na 10b, ampliar a retenção útil sem reduzir as proteções. G já comprova os checks da revisão auditada. |
| L2 | P2 — documentação | `docs/DESIGN.md` e `AGENTS.md` tinham afirmações obsoletas sobre defaults e estado das etapas; a 10a as alinha. Rever referências restantes após mudanças da 10b. |
| L3 | P2 — governança/acesso | A API pública não permitiu ler branch protection (HTTP 401). Confirmar com acesso autorizado se os três checks são exigidos pela `main`; isso não invalida a conclusão observada dos jobs G. |

Não há tag local de `v1.0.0`; não foi consultado o inventário remoto de tags.
A 10b decidirá a versão candidata, fechará B1–B6 e executará os gates sobre
sua revisão final. A confirmação do usuário precede tag e publicação. Nenhuma
campanha acadêmica, conta Azure, Kubernetes ou Processing entra nessa lista.

## Continuação da 10b — bloco 1: dependências e versão

Esta seção acrescenta resultados à auditoria 10a acima, sem alterar suas
classificações históricas. A base inicial do bloco foi
`08df9744bf3ef98a4df077a5d7cf511ae319a7fb`, na branch
`release/phase-10b-v1.0.0`, com árvore limpa. Os resultados abaixo pertencem
à árvore de trabalho modificada a partir dessa base, ainda sem commit; não
foram produzidos pelo SHA limpo. Consulta e validação: **03/10/2026 UTC**.

### B5 — inventário e consulta de advisories de pacotes

`uv.lock` contém 97 entradas: o projeto, 50 pacotes runtime efetivos em
Python 3.14/Linux x86_64 GNU, 42 exclusivos do grupo de desenvolvimento
nessa plataforma e quatro dependências condicionais de outras plataformas.
Os 50 runtime são 15 diretos e 35 transitivos. O grupo de desenvolvimento
possui oito dependências diretas e 54 pacotes na sua árvore, dos quais 12
também integram a árvore runtime. Os comandos de inventário foram:

```bash
uv tree --locked --no-dev --python-version 3.14 --python-platform x86_64-unknown-linux-gnu
uv tree --locked --only-dev --python-version 3.14 --python-platform x86_64-unknown-linux-gnu
```

O lockfile preserva a versão exata de cada pacote.

| Grupo | Versões diretas ou condicionais verificadas no lockfile |
| --- | --- |
| Runtime direto (15) | `alembic==1.20.0`, `azure-storage-blob==12.30.2`, `fastapi==0.141.1`, `opentelemetry-api==1.44.0`, `opentelemetry-exporter-otlp-proto-http==1.44.0`, `opentelemetry-instrumentation-fastapi==0.65b0`, `opentelemetry-sdk==1.44.0`, `pika==1.4.4`, `prometheus-client==0.26.0`, `psycopg==3.3.5` com extra `binary`, `pydantic==2.13.5`, `pydantic-settings==2.15.0`, `python-multipart==0.0.32`, `sqlalchemy==2.0.54`, `uvicorn==0.53.0` |
| Desenvolvimento direto (8) | `httpx2==2.13.0`, `locust==2.46.6`, `mypy==2.3.1`, `pytest==9.1.1`, `pytest-cov==7.1.0`, `ruff==0.16.2`, `taskipy==1.14.1`, `typos==1.49.0` |
| Condicionais ausentes das árvores Linux (4) | `httpx2-jsfetch==1.0`, `mslex==1.3.0`, `pywin32==312`, `tzdata==2026.4` |

Fonte atual: campo `vulnerabilities` da
[API JSON por versão do PyPI](https://pypi.org/pypi/urllib3/2.8.0/json),
alimentado por OSV. As consultas HTTP retornaram `200` para **todos os 96
pacotes externos do lockfile**: 50 runtime efetivos, 42 exclusivos de
desenvolvimento e quatro condicionais. O campo veio vazio para essas versões.
Uma versão antiga conhecida de `urllib3` foi consultada separadamente e
retornou advisories, confirmando que a consulta não ignora esse campo. Os
registros por pacote e versão ficaram também em
`/tmp/docpipe-phase10b-block1-20261003/`; o inventário versionado pode ser
reconstituído pelos comandos acima e por `uv.lock`.

A [API pública de advisories do GitHub](https://docs.github.com/en/rest/security-advisories/global-advisories) respondeu `200`, com `ecosystem=pip` e `affects=nome@versão`, para os cinco itens não concluídos na 10a: `typing-extensions==4.16.0`, `typing-inspection==0.4.4`, `tzdata==2026.4`, `urllib3==2.8.0` e `wrapt==2.4.1`. Nenhum advisory aplicável foi retornado. `tzdata` está no lockfile, mas não é instalado na árvore runtime Linux avaliada. As 45 consultas anteriores do GitHub pertencem à 10a, em 02/10/2026; a consulta atual do PyPI cobre novamente suas versões.

**Resultado deste bloco:** nenhum alerta aplicável foi confirmado para os
pacotes consultados; não houve atualização de dependência. O resultado não
prova ausência absoluta de vulnerabilidades. **B5 permanece aberto**: falta
inventariar digests, componentes e advisories das imagens efetivamente
entregues. As referências declaradas, ainda não avaliadas neste bloco, são
`python:3.14-slim-bookworm`, `ghcr.io/astral-sh/uv:0.9.26`,
`postgres:17.6-bookworm`, `rabbitmq:4.1.4-management` e
`mcr.microsoft.com/azure-storage/azurite:3.37.0`. A imagem final e eventuais
alertas novos serão examinados no bloco 4. Nenhuma imagem foi construída ou
inspecionada neste bloco. O backend de build `uv_build` e o binário uv da
imagem também serão considerados na avaliação do artefato final.

### B6 — versão da candidata

`uv version 1.0.0 --no-sync` atualizou somente a versão do projeto em
`pyproject.toml` e `uv.lock`, de `0.1.0` para `1.0.0`; a revisão do diff não
encontrou alterações nas versões das dependências. O comando de sincronização
da tabela abaixo instalou o projeto `1.0.0` usando o lockfile. A versão
OpenAPI já era `1.0.0` e permaneceu assim. Um teste direcionado agora compara
o OpenAPI aos metadados do pacote instalado e ao alvo `1.0.0`. Uma consulta
independente confirmou `pyproject=lock=instalado=OpenAPI=1.0.0`. O prefixo
`/v1` e o contrato `document.received.v1` não foram modificados.

| Verificação sobre a árvore modificada | Resultado |
| --- | --- |
| `uv sync --locked --group dev` | Exit `0`; projeto `1.0.0` instalado |
| `uv run --locked --no-sync pytest tests/api/test_openapi.py -ra -vv` | Exit `0`; um teste aprovado, sem falhas ou skips |
| `uv run --locked --no-sync task lint` | Exit `0` |
| `uv run --locked --no-sync task format-check` | Exit `0` |
| `uv run --locked --no-sync task typecheck` | Exit `0`; 99 arquivos sem erros |
| `uv run --locked --no-sync typos` | Exit `0`; Markdown é excluído pela configuração atual |
| `uv version --short --locked` e `git diff --check` | Exit `0` em ambos |

**B6 está alinhado e validado nesta árvore de trabalho**, ainda sem commit.
Os gates da candidata final, o build da imagem com esses metadados e os checks
reais de PR/main permanecem para os blocos posteriores. Este bloco não
executou a suíte completa, integrações ou testes packaged.

## Continuação da 10b — bloco 2: limite HTTP antes do parse

Esta seção acrescenta evidências a B1 sem alterar a classificação histórica
da auditoria 10a. A base inicial foi
`89b36e6ba8eccb4bddefc44b6c86a53deceec27c`, em
`release/phase-10b-v1.0.0`, com três linhas preexistentes e preservadas em
`tests/api/test_openapi.py`. Os resultados abaixo são da árvore de trabalho
modificada a partir dessa base, **não** do commit limpo. Data: 03/10/2026 UTC.

A rota de `POST /v1/documents` agora envolve o `receive` usado pelo handler
do FastAPI antes de seu `request.form()`. O corpo total pode ter até
`DOCPIPE_INGESTION_MAX_FILE_SIZE_BYTES + 65.536` bytes: por padrão, 10 MiB
para o arquivo e 64 KiB para o envelope multipart. O limite do arquivo
permanece independente no caso de uso. Um `Content-Length` válido acima do
total permite rejeição sem ler o corpo; em todos os demais casos, os bytes
ASGI recebidos são contados e o chunk que ultrapassa o total não é entregue
ao parser. Nenhum corpo completo é acumulado pela proteção. A resposta
preserva `413`, JSON com `file_too_large`, `X-Correlation-ID` e contadores de
rejeição. A margem comportou uploads válidos nos limites exatos dos testes;
corpos com overhead excessivo são rejeitados mesmo que o arquivo seja menor
que seu próprio limite.

Um teste inicial encontrou aceitação `202` de multipart truncado após um
delimitador intermediário. O parser fixado no lockfile não valida o estado
final em `finalize()`. A rota passou a conferir incrementalmente a presença
do delimitador de fechamento antes de permitir que o parse termine; a
requisição truncada agora recebe `400`. O estado guardado tem tamanho limitado
pelo delimitador, inclusive quando ele se divide entre chunks.

O teste ASGI percorre a aplicação FastAPI completa. Ao exceder o limite após
mais de 1 MiB já gravado em arquivo temporário, confirmou que apenas o
primeiro chunk chegou ao parser, que o arquivo foi fechado e que o caso de
uso não executou. A integração local, com SQLite e armazenamento temporário
explicitamente selecionados para a fixture, confirmou zero blob, documento,
outbox e arquivo `.part` após `413` por excesso do corpo. Esses resultados
não substituem a prova operacional PostgreSQL/Azurite na imagem.

| Verificação sobre a árvore modificada | Resultado |
| --- | --- |
| `uv run --locked --no-sync pytest tests/api/test_body_limit.py -ra -q` (antes da correção do truncamento) | Exit `1`: oito passaram; um mostrou `202` indevido |
| Teste dirigido do multipart truncado após a correção | Exit `0`: dois passaram |
| `uv run --locked --no-sync pytest tests/api/test_documents.py tests/api/test_body_limit.py tests/api/test_health.py tests/application/test_file_validation.py tests/infrastructure/test_observability.py tests/integration/test_documents_api.py -ra -q` | Exit `0`: 66 passaram, sem skips ou falhas |
| `uv run --locked --no-sync task lint`, `task format-check`, `task typecheck`, `typos` | Exit `0` após ajustes de estilo/tipos; `typos` não examina Markdown |
| `git diff --check` | Exit `0`; os dois arquivos novos também não geraram diagnósticos de whitespace na inspeção separada |

**B1 permanece parcial**: falta comprovar `413`, limpeza e ausência de
efeitos por HTTP real na imagem entregue, no bloco 4. Também ficam para os
gates finais da candidata a suíte/cobertura completa e os checks reais de PR.

## Continuação da 10b — bloco 3: concorrência entre reenvio e publicação

Base inicial: `35b39a0422e47383b53b43533262f54048a50b49`, em
`release/phase-10b-v1.0.0`, com a alteração preexistente em
`tests/api/test_openapi.py` preservada. Os resultados de 03/10/2026 UTC
pertencem à árvore de trabalho modificada a partir dessa base, não ao commit
limpo. As integrações usaram um projeto Compose descartável com PostgreSQL,
RabbitMQ e, nos grupos de CI, Azurite. Cada cenário de concorrência criou e
removeu seu próprio banco PostgreSQL, aplicando nele as migrations; cada um
usou fila RabbitMQ isolada e sessões independentes.

O diagnóstico inicial foi confirmado: depois que B confirma o reenvio,
`attempts` é zero. O `UPDATE` condicional de A exige
`attempts >= max_attempts`, e o worker só seleciona
`attempts < max_attempts`. Na ordem original, PostgreSQL rejeitou A sem espera
pelo lock do worker (`pg_blocking_pids` vazio). Não foi demonstrado defeito
de produção; a expectativa de lock do worker foi removida.

As três provas têm objetivos distintos:

1. **Reenvio sem commit:** A mantém o `UPDATE` real sem commit; o worker,
   usando outra sessão, não encontra/publica o evento. Após o commit de A, o
   ciclo seguinte recebe confirm real do RabbitMQ e persiste documento e
   outbox como publicados. Esta prova não é usada para atribuir
   especificamente `SKIP LOCKED`; essa assertion continua em
   `tests/integration/test_postgresql.py`.
2. **Leitura antiga após publicação:** A lê o evento esgotado e pausa; B
   confirma o reenvio; o worker publica e recebe confirm do broker, pausando
   antes do commit PostgreSQL. A retoma seu `UPDATE`, é rejeitado pela
   condição reavaliada sem espera exigida, e o banco ainda mostra o estado
   anterior ao commit do worker. O worker então conclui normalmente. A
   mensagem observada corresponde aos IDs, correlação e payload originais;
   documento e outbox terminam publicados, sem reativação.
3. **Contenção entre reenvios:** A lê o evento esgotado e pausa; B executa o
   `UPDATE` real e pausa antes do commit; o `UPDATE` de A bloqueia. A consulta
   a `pg_stat_activity` identifica PID de A em espera por `Lock` e PID de B
   entre seus `pg_blocking_pids` (na execução final, A=149 e B=150;
   `wait_event=transactionid`, `blockers=[150]`). Depois do commit de B,
   PostgreSQL reavalia a condição e rejeita A. O worker publica depois, com
   confirm real e estado final coerente. Essa prova é contenção entre
   reenvios, não espera pelo lock do worker.

O primeiro grupo de integração revelou interferência de eventos pendentes de
outros testes no banco compartilhado. O harness foi ajustado para criar banco
descartável próprio por cenário. A repetição completa passou. Também foi
corrigido o teste de reenvio que verificava logs `INFO` sem configurar o nível
de captura; ele agora solicita esse nível explicitamente e passa com a
configuração padrão do workflow, preservando as assertions dos campos do log.

| Verificação na árvore de trabalho baseada no commit acima | Resultado |
| --- | --- |
| `pytest tests/integration/test_requeue_publication_race.py` com PostgreSQL/RabbitMQ | Exit `0`: 3 aprovados; JUnit dirigido aceito exigindo os 3 casos |
| Regressões de reenvio, publicação, repositórios, PostgreSQL e RabbitMQ | Exit `0`: 18 aprovados, sem skips; sem `--log-level` adicional |
| Grupo sem serviços do `ci-tests` | Exit `0`: 188 aprovados, 10 excluídos pela seleção, zero skips; JUnit aceito |
| Grupo de integrações do `ci-tests` | Exit `0`: 9 aprovados, 189 excluídos pela seleção, zero skips; JUnit aceito com os cinco módulos existentes e o módulo novo exigido em `=3` |
| JUnit final | `/tmp/docpipe-b3-adjust-20261003/unit-final.xml` e `integration-final.xml`; ambos aceitos pelo verificador |
| Cobertura combinada unitária e integração | 88% (1943 statements, cobertura com branches); `pyproject.toml` não configura percentual mínimo (`fail_under`) |
| `task lint`, `task format-check`, `task typecheck`, `task typos`, `git diff --check` | Exit `0` |

**B3 está comprovado nesta árvore de trabalho.** A cobertura é a da seleção
unitária e integrada desta revisão; não inclui testes `packaged`. A entrega
pelo menos uma vez permanece; as mensagens vistas nestes percursos não
estabelecem garantia geral de entrega única. B4, revisão da imagem e gates
finais continuam reservados aos blocos posteriores.

## Continuação da 10b — subbloco 4A: falha e recuperação

Base avaliada: `d37fd3a525fcdc5ef9860ad75ab9f0703dccd8cd`, branch
`release/phase-10b-v1.0.0`. As evidências abaixo foram produzidas em
03/10/2026 UTC contra a imagem `docpipe-ingestion:phase10b-4a-d37fd3a-worktree`,
ID/digest `sha256:355c08b8d2498ae6b844ab242a48c2cb9e31534863f02233007b3be81f1b553c`.
A imagem contém o código de runtime da candidata nesta base; as alterações
deste subbloco são somente no harness e neste relatório, portanto não foram
incorporadas à imagem. O Compose oficial foi executado no projeto isolado
`docpipe-phase10b-4a`, com PostgreSQL, Azurite, RabbitMQ, API e worker reais.
Os resultados pertencem à árvore de trabalho modificada baseada no SHA
informado, não a um commit limpo. A stack e seus volumes descartáveis foram
removidos após as validações; `docpipe-control-plane` foi preservado.

Os cenários B2 demonstraram que, com Azurite parado, readiness ficou
indisponível e o upload retornou `503 storage_unavailable`, sem novo
documento, evento ou blob. Após a recuperação, readiness voltou, e o
documento e blob aceitos antes da falha continuaram íntegros. Com PostgreSQL
parado, readiness ficou indisponível e o upload retornou
`503 persistence_unavailable`; nenhum documento ou evento novo foi gravado.
O blob produzido antes da falha de persistência foi identificado pela
reconciliação como órfão. O contrato atual exige sua detecção e diagnóstico,
sem remoção automática; o objeto permaneceu disponível para recuperação
operacional. O documento, blob e evento previamente aceitos permaneceram
íntegros. Após restaurar PostgreSQL e reiniciar explicitamente o worker, o
evento pendente foi publicado e persistido como publicado. A recuperação
comprovada é local a esta candidata e não representa failover automático.

O cenário B4 criou um documento e evento pendente, vinculou uma fila isolada
ao exchange real e instalou no banco descartável um constraint trigger
diferido, filtrado pelo ID do evento, para falhar somente o commit que
registraria a publicação. A primeira mensagem foi lida da fila após a
confirmação real do RabbitMQ. A exceção do trigger demonstrou a falha do
commit; consulta PostgreSQL posterior confirmou rollback dos estados do
documento e da outbox, sem novo documento/evento. O trigger foi removido antes
da retomada. O worker reiniciado republicou o mesmo `event_id`, payload e
correlação; o estado final foi persistido como publicado. As duas mensagens
observadas neste teste demonstram a possibilidade legítima de duplicata após
confirmação e falha de commit. O contrato continua sendo entrega pelo menos
uma vez, sem garantia de exactly-once.

| Verificação na árvore de trabalho baseada na revisão acima | Resultado |
| --- | --- |
| B2 dirigido: `DOCPIPE_PACKAGED_SCENARIO=b2` no harness empacotado | Exit `0`: 1 aprovado, sem skips; indisponibilidade, resposta, integridade, órfão reconciliado e retomada verificados |
| B4 dirigido: `DOCPIPE_PACKAGED_SCENARIO=b4` no harness empacotado | Exit `0`: 1 aprovado, sem skips; confirmação, falha real do commit, rollback, duplicata e recuperação verificados |
| Execução padrão de `tests/integration/test_packaged_compose.py -m packaged` | Exit `0`: 1 aprovado em 678,30 s, sem skips; execução integrada completa incluiu B2, B4 e persistência após recriação da stack |
| Verificador JUnit da execução padrão, exigindo `tests.integration.test_packaged_compose=1` | Exit `0`: 1 teste executado e aceito em `/tmp/docpipe-phase10b-4a-full.xml` |
| `uv run --locked task lint` | Exit `0` |
| `uv run --locked task format-check` | Exit `0`: 121 arquivos já formatados |
| `uv run --locked task typecheck` | Exit `0` |
| `uv run --locked typos` | Exit `0` |
| `git diff --check` | Exit `0` |

**B2 e B4 estão comprovados nesta árvore de trabalho.** B2 depende da
reconciliação operacional para localizar o blob órfão; a limpeza automática
não é prometida pelo contrato. B4 confirma a janela de duplicação e a
recuperação transacional, preservando entrega pelo menos uma vez. A validação
foi local e empacotada; não é resultado de GitHub Actions nem de um commit
final de release. B1 permanece parcial até a prova de limite HTTP real
definida para o 4B; B5 continua aberto para a revisão final da imagem e das
imagens de serviço no 4B.
