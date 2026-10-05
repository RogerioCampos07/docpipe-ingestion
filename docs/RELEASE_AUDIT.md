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

## Continuação da 10b — subbloco 4B: HTTP empacotado e revisão de imagens

Revisão avaliada: `8c4c4870f7d762e5638206cf557155fd095940e2`, na branch
`release/phase-10b-v1.0.0`. A árvore contém alterações não commitadas em
`tests/api/test_openapi.py` (alinhamento OpenAPI/pacote, preservado) e
`tests/integration/test_packaged_compose.py` (harness HTTP empacotado e
seleção de healthcheck/recuperação RabbitMQ). Nenhum arquivo de runtime,
Dockerfile, Compose ou lockfile foi alterado no subbloco. Portanto, os
resultados abaixo pertencem à árvore de trabalho identificada, e não ao SHA
limpo. Revisão de fontes e inventários: **04/10/2026 UTC**.

### B1 — limite de corpo em HTTP real

O harness adicionou chamadas TCP HTTP ao serviço API executado na stack
Compose isolada, sem usar `TestClient` para esta prova. A imagem da API e do
worker foi `docpipe-ingestion:phase10b-4a-d37fd3a-worktree`, imagem candidata
local ID/digest `sha256:355c08b8d2498ae6b844ab242a48c2cb9e31534863f02233007b3be81f1b553c`.
Ela contém o runtime B1; a inspeção do diff confirma que a única mudança de
código nesta árvore é no harness, não na aplicação empacotada.

Primeiro, um PDF válido foi enviado por `POST /v1/documents`; a resposta foi
aceita, o worker publicou seu evento, o estado persistido chegou a
`PUBLISHED`, o blob correspondeu aos bytes enviados e a mensagem observada
conservou os identificadores/payload esperados. Em seguida, o harness tirou
um snapshot dos totais de documentos e outbox, nomes de blobs e marcadores
`_uploads/`. Uma requisição cujo `Content-Length` declarava corpo acima do
limite e outra enviada com `Transfer-Encoding: chunked`, sem
`Content-Length`, ultrapassaram `MAX_FILE_SIZE + 64 KiB`. Ambas receberam
`413`, JSON com `error.code=file_too_large`, correlation ID no JSON e no
`X-Correlation-ID`. Os quatro conjuntos de estado permaneceram idênticos ao
snapshot depois de cada rejeição: nenhum documento, evento, blob ou marcador
foi criado. O teste local ASGI da seção do bloco 2 comprova fechamento do
temporário após exceder o limite; o filesystem temporário interno não é
observável pela interface HTTP empacotada e não foi inferido pela ausência
de efeitos externos.

| Verificação na árvore de trabalho acima | Resultado |
| --- | --- |
| Teste dirigido `DOCPIPE_PACKAGED_SCENARIO=b1` | Exit `0`: um teste aprovado, sem skip; JUnit dirigido aceito exigindo `tests.integration.test_packaged_compose=1` |
| Regressões HTTP, limite, validação e observabilidade | Exit `0`: 66 aprovados, zero falhas e skips |
| Gate packaged final `tests/integration/test_packaged_compose.py -m packaged` | Exit `0`: um teste aprovado em 641,02 s, sem skip; incluiu o fluxo B1; JUnit final aceito exigindo o módulo e um caso |
| `task lint`, `task format-check`, `task typecheck`, `typos`, `git diff --check` | Exit `0` após as alterações finais; typecheck reexecutado nesta consolidação: 102 arquivos sem erros |

Tentativas intermediárias do harness tiveram falhas por porta antiga, fila
com mensagem residual e corrida de inicialização do RabbitMQ ao ler
`.erlang.cookie`. Foram corrigidas no harness com seleção da porta configurada,
fila limpa/isolada e recuperação limitada que só prossegue após o erro
específico, healthcheck saudável e conexão AMQP real. A execução final em
stack limpa passou. Os arquivos JUnit usados estão em `/tmp` e são
temporários; os resultados, identidade da imagem e escopo ficam registrados
neste relatório. **B1 está comprovado nesta árvore**, inclusive por HTTP real
na imagem candidata e sem efeitos persistidos da rejeição.

### B5 — imagens e componentes efetivamente entregues

O inventário foi feito sobre imagens locais por ID/digest e sobre os pacotes
instalados nas imagens. As referências e fontes consultadas foram:

| Componente e referência Compose/build | Digest local avaliado | Inventário/versões observadas | Fonte oficial consultada e avaliação |
| --- | --- | --- | --- |
| API/worker `docpipe-ingestion:phase10b-4a-d37fd3a-worktree` | `sha256:355c08b8d2498ae6b844ab242a48c2cb9e31534863f02233007b3be81f1b553c` | Debian 12 Bookworm; 97 pacotes dpkg; Python 3.14.8; dependências runtime Python conforme `uv.lock`; binário uv 0.9.26 permanece na imagem | Debian Security Tracker JSON consultado em 04/10; ver abaixo. Tag base `python:3.14-slim-bookworm` e `ghcr.io/astral-sh/uv:0.9.26` tiveram os manifests oficiais consultados previamente, com digest de índice e plataforma amd64 registrados nos resultados locais. O upstream uv publica releases posteriores (0.12.23 em 03/10); não foi confirmado advisory aplicável ao 0.9.26, mas não houve scanner de binários. |
| PostgreSQL `postgres:17.6-bookworm` | `sha256:f3bd19c606e442c3d7bdfa8002e03fe260a1023351e0ea4598032022b68dd6e3` | Debian 12; 144 pacotes dpkg; PostgreSQL e client `17.6-2.pgdg12+1`; libc6 `2.36-9+deb12u13`; OpenSSL `3.0.17-1~deb12u3` | Debian Security Tracker e release notes oficiais do PostgreSQL `REL_17_STABLE`. Os releases 17.7+ registram correções CVE, incluindo CVE-2025-12818 em libpq; a imagem também contém cliente, portanto o alerta exige triagem da utilização/ameaça, embora o serviço Compose execute como servidor e o Ingestion não use `psql`. A série está em 17.11 (13/08/2026); 17.6 é anterior aos patches e requer revisão antes de considerar a imagem sem alertas. |
| RabbitMQ `rabbitmq:4.1.4-management` | `sha256:294b01e1796a8acede4619f32a1c394fae1f8021e57986ea01aad38dc2a4f502` | Ubuntu 24.04.3 Noble; 110 pacotes dpkg; RabbitMQ 4.1.4; OpenSSL 3.0.13-0ubuntu3.6; OTP 27 | Releases oficiais de `rabbitmq/rabbitmq-server`: 4.1.4 publicado em 02/09/2025 e última manutenção 4.1.x visível 4.1.8 em 22/01/2026; 4.3.6 publicado em 14/09/2026. A página de suporte do publicador respondeu HTTP 403, então EOL/suporte formal não pôde ser confirmado. Não foi executado correlacionador CVE para o inventário Ubuntu, e nenhuma conclusão de ausência de vulnerabilidade é feita. |
| Azurite `mcr.microsoft.com/azure-storage/azurite:3.37.0` | `sha256:830430c1da1a2d537e08f3e6764dd1f5ae00cf0346bcaf625b968ec3f0971fd5` | Alpine 3.23.5; inventário apk local disponível; musl 1.2.5-r23; OpenSSL 3.5.7-r0; Node.js 22.23.2, conforme inventário registrado | Release oficial `Azure/Azurite` v3.37.0, de 26/08. Release 3.36.0 declara atualização da base para Alpine 3.23 e correções de CVEs críticos/de dependências. O índice de pacotes Alpine v3.23 foi consultado em 04/10 (main atualizado 03/10), mas a API oficial `secdb.alpinelinux.org` respondeu 403 e o repositório público `alpinelinux/alpine-secdb` não contém v3.23. Não foi possível correlacionar integralmente cada pacote instalado à secdb da versão. |

As referências declaradas correspondem às imagens Compose efetivamente
iniciadas pelo cenário packaged; API e worker compartilham a imagem DocPipe.
Os manifests foram consultados por `docker buildx imagetools inspect` e os
digests locais confirmados por `docker image inspect`. O Docker Scout não está
instalado (`docker: unknown command: docker scout`); Trivy, Grype e Syft
também não estão disponíveis. Nenhuma dependência ou imagem foi atualizada
neste subbloco.

Para dependências Python, mantém-se a revisão do bloco 1: 96 pacotes externos
no lockfile consultados no PyPI, incluindo os cinco restantes do levantamento
10a, sem advisory retornado pelas fontes consultadas; isso não prova ausência
absoluta. Nenhuma mudança em `pyproject.toml` ou `uv.lock` ocorreu depois
daquela revisão.

O Debian Tracker respondeu com seu conjunto JSON integral. O cruzamento
nominal do inventário Debian das imagens da aplicação e PostgreSQL produziu
entradas `open`/`undetermined` para investigação, não uma lista de
vulnerabilidades confirmadas: algumas descrições têm versão upstream sem
considerar backports Debian, outras afetam utilitários/extensões ou modos não
usados, e o formato do tracker não substitui um scanner que compare cada
pacote binário à distribuição. O PostgreSQL antigo também contém alertas
upstream corrigidos em versões posteriores; a aplicabilidade e a decisão de
atualizar o patch precisam ser registradas antes do fechamento. Para Ubuntu
Noble, a consulta integral por pacote/imagem ainda não foi completada; para
Alpine, a secdb exata não foi acessível. Assim, não há vulnerabilidade
aplicável confirmada nesta revisão, mas também não há base para declarar as
imagens sem vulnerabilidades.

Fontes verificáveis consultadas em 04/10/2026:

- [Debian Security Tracker — dados JSON](https://security-tracker.debian.org/tracker/data/json)
- [PostgreSQL 17 release notes no repositório oficial](https://github.com/postgres/postgres/blob/REL_17_STABLE/doc/src/sgml/release-17.sgml)
- [RabbitMQ releases oficiais](https://github.com/rabbitmq/rabbitmq-server/releases)
- [Ubuntu Security Notices por Noble](https://ubuntu.com/security/notices.json?release=noble) — feed acessível, mas não houve correlação completa por pacote nesta execução
- [Alpine v3.23 APKINDEX oficial](https://dl-cdn.alpinelinux.org/alpine/v3.23/main/x86_64/APKINDEX.tar.gz)
- [Azurite releases oficiais](https://github.com/Azure/Azurite/releases)
- [uv releases oficiais](https://github.com/astral-sh/uv/releases)

**B5 permanece parcial e bloqueia o fechamento da release:** falta completar
a correlação de advisories com versões/aplicabilidade para os inventários
Debian, Ubuntu/Noble e Alpine da imagem final e documentar a decisão sobre
alertas pertinentes, em particular a idade da imagem PostgreSQL 17.6. Nenhum
alerta foi convertido em vulnerabilidade aplicável confirmada sem evidência;
nenhum patch foi aplicado porque esta verificação não confirmou ainda uma
vulnerabilidade aplicável ao uso contratado. A revisão das imagens está
identificada por digest e limitada às imagens efetivamente utilizadas; não
houve atualização de tags nem fixação de digests no Compose.

### Situação dos bloqueadores após o subbloco 4B

| Bloqueador | Estado na árvore avaliada | Evidência/limitação |
| --- | --- | --- |
| B1 | **Resolvido** | Upload aceito e publicado; corpo declarado acima do limite e envio chunked sem comprimento recebem `413`; JSON/correlation corretos e sem mudança nos contadores, blobs ou marcadores; prova packaged final aprovada. |
| B2 | **Resolvido** | Indisponibilidade e recuperação reais de PostgreSQL/Azurite, integridade, reconciliação do blob órfão e retomada registrados no 4A. |
| B3 | **Resolvido** | Três provas determinísticas com PostgreSQL/RabbitMQ reais, incluindo observação de lock e rejeição do reenvio antigo, registradas no bloco 3. |
| B4 | **Resolvido** | Confirm real seguido de falha de commit, rollback e repetição do mesmo evento no 4A; entrega permanece pelo menos uma vez. |
| B5 | **Parcial — bloqueador aberto** | Digests e inventários registrados, mas correlação/aplicabilidade de alertas dos pacotes OS e avaliação equivalente sem scanner não foram concluídas; nenhum advisory aplicável foi confirmado. |
| B6 | **Resolvido** | Pacote, lockfile e OpenAPI em 1.0.0; `/v1` e `document.received.v1` preservados. |

As verificações neste subbloco são locais, contra a árvore modificada e a
imagem identificada. Não são checks de PR nem validação do commit final da
`main`. O fechamento da release e a criação/publicação de tag continuam
dependentes dos gates posteriores e da autorização específica do usuário.

## Continuação da 10b — triagem final de B5

Esta seção complementa a revisão 4B e prevalece para o estado atual de B5.
Na inspeção de **04/10/2026 UTC**, a branch era
`release/phase-10b-v1.0.0`, `HEAD=8a22f8f54d3aafd94783969c66a5d096511d7d74`
(`docs: record phase 10 validation evidence`) e a árvore estava limpa. As
alterações anteriormente relatadas em `docs/RELEASE_AUDIT.md`,
`tests/api/test_openapi.py` e `tests/integration/test_packaged_compose.py`
agora constam em commits anteriores; não foram reescritas. Esta triagem
alterou somente este relatório.

### Inventário confirmado

As imagens foram inspecionadas localmente por digest; contêineres pontuais
foram removidos ao fim de cada leitura. Não foi iniciada a stack Compose nem
reconstruída qualquer imagem.

| Serviço | Referência e digest local efetivamente inventariado | SO e conteúdo observado |
| --- | --- | --- |
| API e worker | `docpipe-ingestion:phase10b-4a-d37fd3a-worktree`, `sha256:355c08b8d2498ae6b844ab242a48c2cb9e31534863f02233007b3be81f1b553c` | Debian 12 Bookworm; 97 pacotes dpkg; Python 3.14.8; `docpipe-ingestion` 1.0.0; 50 distribuições runtime do lockfile mais o projeto; `psycopg`/`psycopg-binary` 3.3.5; `uv` 0.9.26; `ssl.OPENSSL_VERSION` = OpenSSL 3.0.22. |
| PostgreSQL | `postgres:17.6-bookworm`, `sha256:f3bd19c606e442c3d7bdfa8002e03fe260a1023351e0ea4598032022b68dd6e3` | Debian 12 Bookworm; 144 pacotes dpkg; servidor PostgreSQL 17.6 (`17.6-2.pgdg12+1`); `libc6` 2.36-9+deb12u13; `libssl3` 3.0.17-1~deb12u3; `libxml2` 2.9.14+dfsg-1.3~deb12u4; `libpq5` 18.0-1.pgdg12+3. `postgres` carrega `libssl`, `libcrypto`, `libxml2` e `libc`. |
| RabbitMQ | `rabbitmq:4.1.4-management`, `sha256:294b01e1796a8acede4619f32a1c394fae1f8021e57986ea01aad38dc2a4f502` | Ubuntu 24.04.3 Noble; 110 pacotes dpkg; RabbitMQ 4.1.4; Erlang/OTP 27; `libc6` 2.39-0ubuntu8.6; `libssl3t64` 3.0.13-0ubuntu3.6. O crypto NIF do Erlang carrega `/opt/openssl/lib/libcrypto.so.3`, OpenSSL 3.3.5, não o `libcrypto` Ubuntu. |
| Azurite | `mcr.microsoft.com/azure-storage/azurite:3.37.0`, `sha256:830430c1da1a2d537e08f3e6764dd1f5ae00cf0346bcaf625b968ec3f0971fd5` | Alpine 3.23.5; 18 pacotes apk; Azurite 3.37.0; Node.js 22.23.2 com OpenSSL 3.5.7 reportado por `process.versions.openssl`; a biblioteca OpenSSL do Node é estaticamente incorporada. Pacotes apk incluem `musl` 1.2.5-r23 e `libssl3`/`libcrypto3` 3.5.7-r0. |

A imagem DocPipe mantém as referências de build `python:3.14-slim-bookworm`
e `ghcr.io/astral-sh/uv:0.9.26`; os digests locais dos manifests foram
confirmados anteriormente na revisão 4B. As imagens de serviço acima são as
referências do Compose oficial e seus digests foram novamente confirmados
com `docker image inspect`. Os detalhes de cada digest estão no registro
4B, sem fixá-los em Dockerfile ou Compose.

`pyproject.toml` e `uv.lock` não mudaram desde o commit do bloco 1
(`b37cd44`). O inventário da imagem contém 50 dependências runtime mais o
projeto, correspondendo ao lockfile da revisão de dependências. Não há pacote
Python fora daquela revisão nem atualização posterior a ela.

### Debian Bookworm: alertas do Security Tracker

O conjunto JSON do [Debian Security Tracker](https://security-tracker.debian.org/tracker/data/json)
foi consultado em 04/10/2026 e cruzado com `dpkg-query -W` das imagens DocPipe
e PostgreSQL. Foram encontradas 38 entradas `open`/`undetermined` em 11
pacotes da imagem DocPipe e 68 entradas em 13 pacotes da imagem PostgreSQL;
68 identificadores distintos no conjunto. `open` no Tracker é o estado do
registro de segurança da distribuição, não prova isolada de exploração no
serviço. As linhas abaixo agrupam os identificadores para evitar repetir a
mesma evidência de imagem; cada ID foi preservado. O campo `fixed_version`
não estava definido para essas entradas. Quando a urgência Debian era
`unimportant`, isso também é explicitado.

| Imagem/pacote instalado | Alertas e estado Debian/Bookworm | Relação com o uso efetivo; decisão e ação |
| --- | --- | --- |
| DocPipe + PostgreSQL: `apt` 2.6.1 | CVE-2011-3374 (`open`, `unimportant`; sem `fixed_version`) | O caminho descrito é `apt-key`/validação do keyring. O serviço não executa atualização de pacotes em resposta a dados HTTP; **não aplicável ao caminho da aplicação**. |
| DocPipe `bash` 5.2.15-2+b13; PostgreSQL `bash` 5.2.15-2+b9 | TEMP-0841856-B18BAF (`open`, `unimportant`; marcador do Tracker, sem CVE/fix) | Marcador administrativo, sem CVE. Bash não processa o upload; aparece apenas em operações locais do container. **Não é vulnerabilidade confirmada**. |
| DocPipe + PostgreSQL: `coreutils` 9.1-1 | CVE-2016-2781 (`low`); CVE-2017-18018, CVE-2025-5278, CVE-2026-56391, CVE-2026-56392 (`unimportant`); todos `open`, sem `fixed_version` | Os vetores são `chroot`, `chown` recursivo, `sort`, `uniq` e `unexpand`. O fluxo API/worker não invoca esses utilitários com dados do cliente; **não aplicável ao fluxo Compose padrão**. |
| DocPipe + PostgreSQL: `dash` 0.5.12-2 | CVE-2026-102473 (`not yet assigned`); CVE-2026-102474 (`unimportant`), ambas `open`, sem fix | Os vetores são o matcher `*` sem `fnmatch` e expansão `printf` Unicode em shell. O `setup` usa shell apenas para comandos fixos; nenhum campo de upload é interpretado como shell. **Não aplicável ao fluxo documentado**. |
| DocPipe + PostgreSQL: `diffutils` 1:3.8-4 | CVE-2026-53910 (`unimportant`, `open`, sem fix) | Vulnerabilidade no utilitário `diff3`; não executado pela API, worker ou setup. **Não aplicável**. |
| DocPipe + PostgreSQL: `gzip` 1.12-1 | CVE-2026-41991 e CVE-2026-41992 (`open`, sem urgência/fix atribuídos) | Um caso afeta `gzexe`, outro a descompressão LZH. O Ingestion não descompacta uploads nem executa `gzexe`; **não aplicável ao fluxo**. |
| DocPipe `libgcrypt20` 1.10.1-3+deb12u1; PostgreSQL 1.10.1-3 | CVE-2018-6829 e CVE-2024-2236 (`unimportant`, `open`, sem fix) | Os cenários descritos dependem de uso de ElGamal ou operações RSA suscetíveis. Não foi encontrado vínculo dinâmico com os processos de serviço; uso fica em utilitários auxiliares. **Não aplicável ao processo de serviço**. |
| DocPipe + PostgreSQL: `libtasn1-6` 4.19.0-2+deb12u1 | CVE-2025-13151 (`open`, sem urgência/fix atribuídos) | O pacote não é carregado pelo Python/OpenSSL da aplicação nem pelos binários `postgres`/RabbitMQ inventariados; **não aplicável ao processo de serviço**. |
| DocPipe: `openssl` 3.0.22-1~deb12u1; PostgreSQL: 3.0.17-1~deb12u3 | CVE-2025-27587, CVE-2026-35189, CVE-2026-54872, CVE-2026-75805, CVE-2026-75806, CVE-2026-77696, CVE-2026-84782 (todos `open`, sem `fixed_version`) | CVE-2025-27587 é específico da arquitetura PowerPC; os demais registros upstream são restritos a CRL, CMP, DTLS, SM2 ou DTLS retransmission. A aplicação não usa esses recursos no Compose padrão. A imagem PostgreSQL carrega OpenSSL para conexão SQL, mas a triagem não provou se a configuração efetiva negocia TLS nem se algum desses caminhos pode ser atingido; **evidência insuficiente para fechar aplicabilidade em PostgreSQL**. O Tracker lista pacotes Bookworm atuais até `3.0.22-1~deb12u1`; a imagem PostgreSQL está em 3.0.17. Próximo passo: usar imagem PostgreSQL com pacote atualizado e reavaliar o protocolo configurado ou obter prova do caminho TLS. |
| DocPipe + PostgreSQL: `tar` 1.34+dfsg-1.2+deb12u1 | CVE-2005-2541, CVE-2026-18477, CVE-2026-18508, CVE-2026-5704 e TEMP-0290435-0B57B5 (CVE-2005 e TEMP `unimportant`; demais sem classificação; `open`, sem fix) | Riscos nos modos de extração/backup de tar; uploads não são extraídos e o serviço não cria arquivos de backup via `tar`. O marcador TEMP não é CVE. **Não aplicável ao fluxo**. |
| DocPipe + PostgreSQL: `util-linux` 2.38.1-5+deb12u3 | CVE-2022-0563, CVE-2025-14104 (`unimportant`) e CVE-2026-13595, CVE-2026-27456, CVE-2026-3184, CVE-2026-53613, CVE-2026-53615, CVE-2026-76642, CVE-2026-78408, CVE-2026-78409, CVE-2026-78410 (demais sem urgência); todos `open`, sem fix | Os avisos descrevem ferramentas/funções de login, mount, namespace e probing de discos. O container não expõe essas operações aos dados HTTP; **não aplicável ao serviço**. |
| PostgreSQL: `libxml2` 2.9.14+dfsg-1.3~deb12u4 | CVE-2026-11979, CVE-2026-6653, CVE-2026-74860, CVE-2026-76781, CVE-2026-86137 a CVE-2026-86144 (todos `open`, sem `fixed_version`) | O processo PostgreSQL carrega libxml2 e oferece suporte a funções XML; a API atual não traduz upload ou metadados em SQL/XML e não fornece execução arbitrária de SQL. Os cenários de `xmlcatalog`, bindings Python, regex XML e parse de conteúdo XML não são alcançados pelo contrato Ingestion. **Não aplicável ao caminho HTTP atual**, mas depende da manutenção da fronteira sem SQL arbitrário. |
| PostgreSQL: `perl` 5.36.0-7+deb12u3 | CVE-2011-4116, CVE-2023-31486, CVE-2025-15649, CVE-2026-12087, CVE-2026-13221, CVE-2026-15534, CVE-2026-19487, CVE-2026-42496, CVE-2026-42497, CVE-2026-48959, CVE-2026-48962, CVE-2026-57432, CVE-2026-57433, CVE-2026-7010, CVE-2026-7017, CVE-2026-82560, CVE-2026-8376, CVE-2026-9538 (mistura de `unimportant` e `not yet assigned`; `open`, sem fix) | Os registros pertencem ao runtime/utilitários Perl, arquivos tar, regex, HTTP::Tiny e módulos auxiliares. PostgreSQL executa o servidor C; a aplicação não executa Perl nem entrega scripts a esse runtime. **Não aplicável ao fluxo do serviço**. |

O upstream PostgreSQL registra correções de segurança em patch releases
posteriores ao 17.6. As notas oficiais da série `REL_17_STABLE` listam
CVE-2025-12817/12818 em 17.7; CVE-2026-2003/2004/2005/2006 em 17.8;
CVE-2026-6472 a 6479 e CVE-2026-6637/6638 em 17.10; e
CVE-2025-8714, CVE-2026-14662 a 14664, 14666, 14668 a 14673, 14677 a
14681, 15741/15742, 16239/16241, 18024, 18408, 19385, 6464, 6469 a
6471, 6473 e 6637 em 17.11. As mesmas notas registram que alguns itens são
específicos de funções como libpq, `pgcrypto`, `refint` ou replicação lógica.
O processo PostgreSQL está acessível somente na porta localhost da stack; a
API não expõe SQL. O major 17 segue suportado, mas 17.6 é uma revisão antiga
frente à 17.11 publicada. A idade da imagem, por si só, não prova
aplicabilidade desses CVEs ao Ingestion.

### Ubuntu Noble, RabbitMQ e suporte do broker

O endpoint oficial [Ubuntu Security Notices para Noble](https://ubuntu.com/security/notices.json?release=noble)
foi consultado com paginação até os 1.544 avisos. Os pacotes instalados foram
comparados com as versões Noble corrigidas informadas nos avisos. Entre as
atualizações de segurança que atingem componentes da imagem estão:

| IDs e pacotes | Versão instalada → versão corrigida | Aplicabilidade observada; decisão/ação |
| --- | --- | --- |
| USN-8005-1 — CVE-2026-0861, CVE-2026-0915, CVE-2025-15281, CVE-2025-8058 (`libc6`, `libc-bin`) | 2.39-0ubuntu8.6 → 2.39-0ubuntu8.7 | `libc6` é dependência dinâmica do runtime Erlang. As descrições oficiais requerem argumentos específicos de `memalign`, NSS/DNS, `wordexp` ou falha de alocação em regex; a configuração não habilita reverse DNS e os uploads não viram essas entradas. **Sem caminho de exploração demonstrado**; risco residual de componente base desatualizado documentado. |
| USN-8611-1 — CVE-2026-5450, 4438, 5928, 6238, 4437, 4046, 5435 (`libc6`, `libc-bin`) | 2.39-0ubuntu8.6 → 2.39-0ubuntu8.8 | Os paths são `%mc` com width excessiva, NSS/DNS, wide chars, funções DNS obsoletas e conjuntos de caracteres IBM. Não são acionados pelo protocolo AMQP/HTTP habilitado na stack; NSS reverso está desabilitado. **Não aplicável ao uso configurado**, com a mesma limitação de pacote glibc antigo. |
| USN-8737-2 — CVE-2026-77117, 19499, 6791, 19542, 6368, 80489 (`libc6`, `libc-bin`) | 2.39-0ubuntu8.6 → 2.39-0ubuntu8.9 | Os paths exigem conversão de conjuntos japoneses específicos, formatação monetária, expansão de caminho `~`, `tdelete` ou `wordexp`. Nenhum é exposto por configuração nem pelo fluxo do broker. **Não aplicável ao caminho configurado**; `.9` é a versão cumulativa atual indicada nas fontes consultadas. |
| USN-7980-1, 8155-1, 8414-1, 8625-1, 8678-1, 8847-1 — avisos OpenSSL para CVEs em OpenSSL OS (`libssl3t64`/`openssl`) | 3.0.13-0ubuntu3.6 → até 3.0.13-0ubuntu3.16 | O processo Erlang não carrega a biblioteca OpenSSL Ubuntu: o crypto NIF resolve `/opt/openssl/lib/libcrypto.so.3`, versão 3.3.5; o listener RabbitMQ/management no Compose é AMQP/HTTP sem TLS. **Os avisos do pacote Ubuntu não se aplicam ao caminho do serviço**. O OpenSSL próprio do Erlang é triado separadamente abaixo. |
| USNs para Python 3.12, coreutils, diffutils, dpkg, gzip, libexpat, GnuTLS, zlib, Perl, tar e util-linux | Ex.: Python 3.12.3-1ubuntu0.8 com avisos corrigidos até 1ubuntu0.17; cada USN informa sua versão fixa | Esses runtimes/utilitários não executam o broker nem processam a mensagem. O RabbitMQ usa Erlang/OTP 27; nenhum serviço Python é iniciado na imagem. **Não aplicável ao fluxo de serviço**, embora as versões existam na imagem. |

As páginas oficiais Ubuntu por CVE confirmam, entre outros exemplos,
CVE-2026-0861 corrigido em Noble em `2.39-0ubuntu8.7`; CVE-2026-5450 em
`.8`; e CVE-2026-77117 em `.9`. Os avisos listam correção para o pacote,
mas a análise de função/caminho não identificou entrada controlável no
Ingestion que alcance essas rotinas. A imagem pode ser atualizada para
reduzir exposição geral do sistema, mas esta auditoria não classifica esses
CVEs como vulnerabilidades aplicáveis ao protocolo e configuração local.

Há, porém, uma limitação de suporte confirmada no componente de serviço:
segundo a [matriz oficial de releases RabbitMQ](https://github.com/rabbitmq/rabbitmq-website/blob/main/docusaurus.config.js),
a série 4.1 encerrou suporte comunitário em **31/01/2026**; a 4.1.4 é de
02/09/2025, e a última manutenção 4.1.x listada é 4.1.8 (22/01/2026). A
matriz informa suporte comercial indicativo até 30/04/2027, sujeito a
licença. A candidata local não declara licença comercial; portanto, deve ser
tratada como fora de suporte comunitário. Em 04/10/2026, a 4.3 era a série
comunitária mais nova, com 4.3.6 e fim de suporte comunitário previsto para
30/11/2026. A decisão exigida é atualizar o broker para uma série comunitária
suportada na data de fechamento, ou apresentar autorização explícita de
suporte comercial/aceitação de risco. Como o usuário proibiu alterar imagem
nesta triagem, nenhuma atualização foi feita.

### OpenSSL 3.3.5 do RabbitMQ e 3.5.7 do Azurite

As [releases oficiais OpenSSL](https://github.com/openssl/openssl/releases)
confirmam que:

| Componente embarcado | Instalada → patch releases oficiais | CVEs destacados na release corrigida | Uso configurado e decisão |
| --- | --- | --- | --- |
| RabbitMQ/Erlang `/opt/openssl` | 3.3.5 (30/09/2025) → 3.3.6 (27/01/2026) e 3.3.7 (07/04/2026) | 3.3.6: CVE-2025-15467, 15468, 66199, 68160, 69418, 69419, 69420, 69421, CVE-2026-22795/22796. 3.3.7: CVE-2026-31790, 28387, 28388, 28389, 28390, 31789. | As correções são para CMS, TLS 1.3 Certificate Compression, funções SSL, BIO, OCSP/ASN.1, DANE e RSA-KEM. TLS não está habilitado nos listeners do Compose; essas interfaces não são usadas pelo fluxo. **Não aplicável ao protocolo local configurado**. Ainda assim, a imagem RabbitMQ precisa ser substituída pela série suportada por fim de suporte comunitário, e o novo digest deverá receber nova triagem. |
| Azurite/Node.js | 3.5.7 embarcado (Node 22.23.2) → OpenSSL 3.5.8 (25/08/2026) e 3.5.9 (29/09/2026) | 3.5.8: CVE-2026-18798, 63072, 63076, 14456, 14457, 54874, 63073, 63074, 63075, 75803. 3.5.9: CVE-2026-84782, 35189, 35191, 42772, 54872, 54873, 54875, 72897, 75804, 75805, 75806, 77696, 84784. | As notas oficiais descrevem QUIC, DTLS, CMS/CMP, CRL, SM2 e APIs de cifras. O Azurite do Compose escuta HTTP sem TLS; a API de blobs não invoca esses protocolos/formats. **Não aplicável ao percurso HTTP configurado**. |

O índice oficial Alpine v3.23 foi obtido em 04/10 (índice `main` atualizado
em 03/10); nele `musl` continua em 1.2.5-r23, mas `libssl3`/`libcrypto3`
3.5.7-r0 já têm 3.5.9-r0, e o índice também contém Alpine 3.23.6,
`apk-tools`/`libapk` 3.0.8 e certificados mais novos. A secdb oficial em
`secdb.alpinelinux.org` respondeu HTTP 403; o repositório público
`alpinelinux/alpine-secdb` não contém a secdb 3.23. O inventário APKINDEX não
é uma fonte de status CVE. A análise de OpenSSL acima usa as notas do
publicador e a interface HTTP observada do Azurite. Não há advisory aplicável
confirmado para o uso HTTP, mas a secdb integral da imagem continua como
limitação de cobertura.

### Dependências Python e conclusão de B5

Não há mudança no lockfile após `b37cd44`; a imagem candidata contém somente
as 50 dependências runtime travadas e o próprio pacote. Mantém-se a consulta
PyPI/Global Security Advisories da revisão do bloco 1 para essas versões,
sem advisories retornados pelas fontes consultadas; isso não significa
ausência absoluta de vulnerabilidades.

**B5 permanece aberto — requisito de release ainda não atendido.** A triagem
deu decisão aos grupos de avisos do Debian e Ubuntu e aos CVEs OpenSSL dos
protocolos não usados; nenhum foi confirmado aplicável ao fluxo HTTP/AMQP
atual. Ainda assim, a imagem RabbitMQ 4.1.4 está fora do suporte comunitário,
e as imagens incluem correções de segurança disponíveis para componentes de
base, em particular glibc do RabbitMQ e bibliotecas do PostgreSQL. O caminho
PostgreSQL/OpenSSL requer confirmar o modo TLS efetivo ou validar com imagem
atualizada; a secdb Alpine também não pôde ser obtida. Assim, não declaro as
imagens sem vulnerabilidades nem fecho o bloqueador com base na ausência de
scanner.

**Decisão para a próxima execução, sujeita à revisão do usuário:** selecionar
uma imagem RabbitMQ de série comunitária suportada na data do fechamento e
uma imagem PostgreSQL com patch 17.x e pacotes Bookworm atualizados; repetir
inventário por digest, triagem dos alertas residuais e testes packaged
afetados. Se uma série suportada ou pacote corrigido não puder ser adotado,
registrar aceitação explícita com o impacto local. Não foram alteradas
imagens, Compose, Dockerfile, dependências ou código nesta triagem.

## Execução autorizada — correção final de B5 (05/10/2026)

Esta seção atualiza e prevalece sobre as decisões provisórias acima. Execução
na branch `release/phase-10b-v1.0.0`, com `HEAD`
`8a22f8f54d3aafd94783969c66a5d096511d7d74`. Antes da edição, a única
alteração local era a seção desta auditoria já existente e modificada pelo
usuário. Ela foi preservada. Não houve alteração de código de produção,
Dockerfile, dependências Python ou lockfile.

### RabbitMQ: versão, suporte e conteúdo observado

As referências operacionais `rabbitmq:4.1.4-management` foram atualizadas
para `rabbitmq:4.3.6-management` em `docker-compose.yml`,
`docker-compose.experiments.yml` e no inventário de imagens de
`experiments/lab.py`. Não foi localizada outra referência operacional
ativa. As menções à imagem antiga nesta auditoria permanecem como evidência
histórica da inspeção anterior.

Em **05/10/2026 UTC**, a matriz oficial de releases identificava `4.3.6`
como patch estável atual da série 4.3. A política publica suporte comunitário
até **30/11/2026**. A release oficial `v4.3.6` foi publicada em 14/09/2026.
Portanto, a imagem está suportada na data desta consulta, mas sua janela
restante é curta (56 dias): acompanhar a manutenção e escolher a próxima
série suportada antes de 30/11/2026. A curta janela não bloqueia esta
validação local.

Fontes oficiais consultadas:

- [matriz e datas de suporte do RabbitMQ](https://github.com/rabbitmq/rabbitmq-website/blob/main/docusaurus.config.js)
- [release RabbitMQ 4.3.6](https://github.com/rabbitmq/rabbitmq-server/releases/tag/v4.3.6)
- [política de releases RabbitMQ](https://www.rabbitmq.com/release-information)

| Imagem | Digest efetivamente inspecionado | Resultado relevante |
| --- | --- | --- |
| Anterior: `rabbitmq:4.1.4-management` | `sha256:294b01e1796a8acede4619f32a1c394fae1f8021e57986ea01aad38dc2a4f502` | Série 4.1 fora do suporte comunitário desde 31/01/2026. |
| Atual: `rabbitmq:4.3.6-management` | `sha256:316ffd2a847e59112eee2c65f04bbd0989d93aaf1486c07b721f8d22d863b968` (`linux/amd64`; `docker.io/library/rabbitmq@sha256:316ffd2a847e59112eee2c65f04bbd0989d93aaf1486c07b721f8d22d863b968`) | Pull em 05/10/2026; `rabbitmqctl version` informou 4.3.6. Ubuntu 24.04.5; `libc6` 2.39-0ubuntu8.9; OpenSSL do sistema 3.0.13-0ubuntu3.16; OpenSSL embarcado em `/opt/openssl` 3.5.9 (29/09/2026). |

A atualização também substitui, na imagem RabbitMQ, as versões Noble antigas
registradas na tabela de USNs: `libc6` agora está em `2.39-0ubuntu8.9` e
`libssl3t64` em `3.0.13-0ubuntu3.16`, que correspondem às versões corrigidas
mais recentes indicadas nas fontes Ubuntu consultadas para os alertas
agrupados ali. O Erlang informa OpenSSL embarcado 3.5.9; as correções oficiais
3.5.8/3.5.9 cobrem as CVEs listadas na revisão anterior para QUIC, DTLS,
CMP, CRLDP, CMS, handshakes TLS, SM2 e APIs AEAD. O listener usado pelo
Compose permanece AMQP/HTTP sem TLS; não se atribui ao broker uso de QUIC,
DTLS, CMP, CMS ou SM2. A imagem também foi atualizada para uma série com
suporte comunitário vigente. O digest novo, portanto, substitui a decisão
anterior baseada no OpenSSL 3.3.5 e recebe esta nova triagem.

O OpenSSL 3.5.7 do Azurite e os alertas já agrupados para seu Node.js foram
revisados contra o uso observado: Azurite serve HTTP na porta de blob, sem
TLS, QUIC, DTLS, CMP, CMS ou SM2 configurados. Isso fundamenta a não
aplicabilidade desses vetores ao fluxo local observado; não equivale a uma
declaração de ausência de vulnerabilidades na imagem Alpine. A limitação da
secdb Alpine anteriormente registrada (resposta HTTP 403) permanece.

### Compose isolado e provas do broker

As configurações foram validadas antes do pull: `docker compose config
--quiet` passou para a stack principal, o Compose de experimentos e as
variantes `api-scale` e `worker-scale`. O pull da imagem 4.3.6 terminou com
o digest acima. A imagem da aplicação foi construída como
`docpipe-ingestion:b5-validation-20261005`, sem mount do checkout nos
containers de serviço.

A validação usou exclusivamente o projeto Compose
`docpipe-b5-20261005`, portas locais `18080` (API), `19081` (métricas do
worker), `25432` (PostgreSQL), `25672`/`25673` (RabbitMQ) e `20000`
(Azurite), com rede e volumes nomeados próprios. PostgreSQL, Azurite e
RabbitMQ iniciaram limpos e saudáveis; migrations foram aplicadas à base
vazia; API e worker empacotados ficaram saudáveis. A prova empacotada
exercitou publicação, recuperação, reenvio e reinício.

A primeira execução empacotada falhou apenas na reconciliação de uploads
incompletos porque a chamada não definiu
`DOCPIPE_INGESTION_INCOMPLETE_FILE_AGE_SECONDS=1`, valor configurado pelo
job `ci-image`. Descartei somente os volumes/rede/containers desse projeto,
recriei a stack limpa com esse valor e repeti a prova. Resultado final:
`1 passed` em 206,51 s. O verificador
`.github/scripts/verify_pytest_junit.py --require-module
tests.integration.test_packaged_compose=1` aprovou o JUnit.

As regressões diretamente afetadas passaram na mesma stack: `test_rabbitmq.py`
e os três casos de `test_requeue_publication_race.py` (publisher confirms,
publicação e retomada/reenvio): **4 passed** em 1,96 s.

### PostgreSQL local: conexões, TLS e exposição

O Compose local não define `sslmode` nas URLs. API, worker e comando de
migrations recebem o mesmo
`postgresql+psycopg://...@postgres:5432/...`; o Compose de experimentos usa
URL equivalente. Os testes empacotados e CI usam a porta publicada no host,
também sem `sslmode`. O libpq incluído no adaptador `psycopg` informa versão
18.6 (`psycopg.pq.version() == 180006`); seu default `prefer` não negocia TLS
quando o servidor anuncia SSL desligado.

Evidência coletada com PostgreSQL 17.6 real, enquanto API e worker estavam
ativos no projeto isolado:

- `SHOW ssl` → `off`; `SHOW listen_addresses` → `*` dentro do container.
- `pg_stat_activity JOIN pg_stat_ssl` mostrou sessões da API
  (`172.21.0.6`) e worker (`172.21.0.5`) com `ssl=false`, sem versão ou
  cifra TLS. Repetição após as provas mostrou as mesmas sessões sem TLS.
- `pg_extension` contém somente `plpgsql`; `pgcrypto` não está instalado.
- O mapeamento Docker da porta do banco foi
  `127.0.0.1:25432 -> 5432`. Uma conexão pelo loopback do host teve sucesso;
  conexões aos endereços das bridges do host (`172.21.0.1` e `172.17.0.3`)
  foram recusadas. Assim, a porta publicada pode ser acessada por processos
  do próprio host e por serviços conectados à rede Compose; não foi
  publicada em interface externa nem está acessível por esses endereços do
  host. A rede Compose continua sendo uma fronteira compartilhada entre seus
  containers.

Conclusão de transporte: **API, worker, migrations e clientes de teste não
usam TLS com o PostgreSQL local**. A exposição é limitada ao host local e à
rede interna Compose, com credenciais locais sintéticas; a senha local do
Compose não é autenticação apropriada para produção. Isso não comprova
requisito de TLS em produção. O RNF-004 exige TLS para produção; não habilitei
TLS nem alterei a arquitetura local nesta triagem.

Os alertas OpenSSL do PostgreSQL foram reavaliados contra a versão instalada
(`libssl3` 3.0.17-1~deb12u3 na imagem `postgres:17.6-bookworm`) e o transporte
real. As correções citadas anteriormente afetam CMS, CMP, DTLS, CRLDP,
handshake TLS, SM2 e uso de cifras AEAD. Com `ssl=off`, nenhuma sessão de
serviço alcança as rotinas de TLS/DTLS ou validação de certificado; CMP,
CMS, SM2 e `pgcrypto` também não fazem parte do percurso configurado. Não
classifiquei o alerta automaticamente como irrelevante: esta decisão usa a
prova de `ssl=off`, `pg_stat_ssl=false`, extensão instalada e porta publicada
somente no loopback, além da ausência de SQL arbitrário no contrato HTTP.
Ainda assim, a versão Bookworm/OpenSSL da imagem é antiga e uma revisão de
patch da imagem continua indicada.

### Conclusão atualizada de B5

**B5 permanece aberto.** A pendência do RabbitMQ está resolvida: a imagem
usada é suportada comunitariamente na data da consulta, tem digest registrado
e as provas empacotadas e de publicação/recuperação passaram. A utilização
efetiva de TLS no PostgreSQL foi comprovada como inexistente e sua exposição
local foi documentada; os alertas de protocolo TLS foram avaliados contra
essa evidência.

Resta uma vulnerabilidade de servidor PostgreSQL na imagem mantida nesta
triagem. O PostgreSQL 17.6 está abaixo da versão corrigida 17.7 para
[CVE-2025-12817](https://github.com/CVEProject/cvelistV5/blob/main/cves/2025/12xxx/CVE-2025-12817.json): a falha de autorização em `CREATE STATISTICS`
permite a um dono de tabela criar estatísticas em schema sem privilégio
`CREATE`, causando negação de serviço para outro usuário que tente criar o
mesmo nome. O serviço não expõe SQL arbitrário pelo HTTP e a porta do banco
não é publicada fora do loopback, mas API/worker usam a role proprietária
`docpipe` e o banco é alcançável pelos serviços da rede Compose e pelo host.
Não considero a versão do servidor sem correção aceitável para fechar a
revisão de segurança. Não atualizei a imagem PostgreSQL, conforme o limite
desta execução; a correção exige adotar um patch 17.x e refazer as provas e o
inventário antes de resolver B5.

Separadamente, CVE-2025-12818 afeta `libpq` anterior a 18.1. O processo
PostgreSQL é servidor, não usa essa biblioteca cliente no caminho de
execução; o cliente da aplicação reportou libpq 18.6. O `libpq5` 18.0
presente na imagem do servidor integra ferramentas cliente e permanece uma
observação de inventário, sem ser o cliente utilizado por API/worker.

### Checks e encerramento dos recursos

| Verificação | Resultado |
| --- | --- |
| `docker compose config --quiet` (4 stacks/variantes) | passou |
| Pull RabbitMQ 4.3.6 e inicialização limpa / migrations / API / worker | passou |
| Prova empacotada obrigatória | passou, 1 teste |
| Verificador JUnit obrigatório | passou, 1 teste obrigatório executado |
| Regressões RabbitMQ/publicação/reenvio | passou, 4 testes |
| `uv run --locked task lint` | passou |
| `uv run --locked task format-check` | passou, 121 arquivos formatados |
| `uv run --locked task typecheck` | passou, 102 arquivos sem erros |
| `uv run --locked task typos` | passou |
| `git diff --check` | passou, sem erros |

Ao final, foram removidos somente os containers, volumes e rede do projeto
isolado `docpipe-b5-20261005` e as tags `docpipe-ingestion:b5-validation-20261005`
e `rabbitmq:4.3.6-management` criadas/usadas pela validação. O container
externo `docpipe-control-plane` foi observado ativo antes e depois e
permaneceu ativo; nenhum outro recurso foi removido.

## Fechamento de B5 — PostgreSQL 17.11 (05/10/2026 UTC)

Esta decisão complementa e prevalece sobre a conclusão provisória de B5
registrada acima. A validação ocorreu na branch
`release/phase-10b-v1.0.0`, inicialmente em
`HEAD=8a22f8f54d3aafd94783969c66a5d096511d7d74`. Foram preservadas as
alterações locais preexistentes de RabbitMQ, TLS e auditoria. Nenhum código de
produção, contrato, migration, dependência Python, Dockerfile, configuração
TLS ou arquitetura foi alterado.

### Correção e identidade da imagem

As três referências operacionais agora usam `postgres:17.11-bookworm`:
`docker-compose.yml`, `docker-compose.experiments.yml` e o inventário em
`experiments/lab.py`. A busca no repositório não encontrou outra referência
operacional a `17.6-bookworm`; as referências antigas neste relatório são
históricas e descrevem a imagem anteriormente triada.

Fontes primárias consultadas em 05/10/2026 UTC:

- [CVE Project — CVE-2025-12817](https://github.com/CVEProject/cvelistV5/blob/main/cves/2025/12xxx/CVE-2025-12817.json): descreve a falha de autorização em `CREATE STATISTICS` e identifica PostgreSQL 17 anterior a 17.7 como afetado.
- [Notas oficiais PostgreSQL 17.7](https://github.com/postgres/postgres/blob/REL_17_STABLE/doc/src/sgml/release-17.sgml): registram a verificação de privilégio `CREATE` no schema, correção correspondente à CVE.
- [Índice oficial das imagens Docker PostgreSQL](https://github.com/docker-library/official-images/blob/master/library/postgres): lista `17.11-bookworm` como imagem oficial da série 17 para Bookworm.
- [Docker Hub — metadados da tag](https://hub.docker.com/layers/library/postgres/17.11-bookworm/images/sha256-639ab7ceb90e13123085b741fb31ef493fba25463002f6da665352e7b534b652): digest e status da tag consultados na data da validação.

| Referência | Digest/identidade | Evidência |
| --- | --- | --- |
| Anterior: `postgres:17.6-bookworm` | Manifesto anteriormente inventariado: `sha256:f3bd19c606e442c3d7bdfa8002e03fe260a1023351e0ea4598032022b68dd6e3` | PostgreSQL 17.6, abaixo da primeira correção 17.7 para CVE-2025-12817. |
| Testada: `postgres:17.11-bookworm` | Manifesto recebido: `sha256:639ab7ceb90e13123085b741fb31ef493fba25463002f6da665352e7b534b652`; imagem local `linux/amd64`, ID `sha256:639ab7ceb90e13123085b741fb31ef493fba25463002f6da665352e7b534b652` | `docker pull` recebeu o mesmo digest informado na consulta do planejamento. O container confirmou `PostgreSQL 17.11 (Debian 17.11-1.pgdg12+2)` e `/etc/os-release` confirmou Debian GNU/Linux 12 (Bookworm). Não houve divergência de digest. |

As notas oficiais de 17.11 também foram consideradas. A alteração de plugins
de logical decoding não alcança a configuração atual: não há slots de
replicação (`pg_replication_slots` retornou zero). A extensão instalada é
somente `plpgsql`; `pgcrypto` não está instalado. Nenhuma incompatibilidade
de migrations ou de execução foi observada. Considerando a triagem de
componentes e vetores nas seções anteriores, o protocolo usado e a fronteira
sem SQL arbitrário, não foi identificada outra vulnerabilidade aplicável ao
fluxo atual. Isso não afirma ausência absoluta de vulnerabilidades nem
substitui a manutenção e a revisão periódica das imagens.

### Validação integrada

A validação usou o projeto isolado
`docpipe-b5-postgres-20261005`, rede e volumes próprios, e portas de loopback
`18080` (API), `19081` (métricas do worker), `25432` (PostgreSQL),
`25672`/`25673` (RabbitMQ) e `20000` (Azurite). Foram usados volumes novos.
O digest da imagem de aplicação reutilizada foi
`sha256:355c08b8d2498ae6b844ab242a48c2cb9e31534863f02233007b3be81f1b553c`,
previamente inventariado; a implementação da aplicação permaneceu igual à
candidata já auditada.

| Verificação | Resultado |
| --- | --- |
| Compose principal, perfis `api-scale` e `worker-scale`, Compose experimental e seus dois perfis | passou, seis configurações com `docker compose config --quiet` |
| Pull e identificação PostgreSQL | passou; tag, manifesto, arquitetura, variante Bookworm e versão 17.11 registrados acima |
| PostgreSQL, Azurite e RabbitMQ em projeto/volumes novos | passou; os três health checks ficaram saudáveis |
| Migrations Alembic | passou em base vazia; revisões aplicadas até `20260918_03` |
| API e worker | passou; ambos ficaram saudáveis na stack empacotada |
| API, armazenamento privado e outbox | passou na prova empacotada com PostgreSQL, Azurite e RabbitMQ reais |
| Publicação, confirmação, reenvio e reinício | passou no cenário empacotado obrigatório |
| Teste Compose empacotado | `1 passed`, 197 itens não selecionados, em 221,53 s; nenhum skip |
| Verificador JUnit | passou; confirmou um caso executado e sem falhas, erros ou skips |
| `uv run --locked task lint` | passou |
| `uv run --locked task format-check` | passou, 121 arquivos formatados |
| `uv run --locked task typecheck` | passou, 102 arquivos sem erros |
| `uv run --locked task typos` | passou |
| `git diff --check` | passou |

Houve duas tentativas iniciais não aprovadas pelo harness: a primeira não
definiu a URL PostgreSQL de teste obrigatória; na seguinte, o worker foi
iniciado antes da asserção que exige eventos ainda pendentes. Nenhuma delas
comprovou o cenário. Os recursos desse projeto foram removidos e a prova foi
recriada em volumes vazios, com URLs explícitas e o worker parado antes do
teste; a execução listada na tabela é a repetição completa aprovada.

### TLS local e decisão

O PostgreSQL local continua sem TLS: `SHOW ssl` retornou `off`; durante a
verificação, `pg_stat_ssl` mostrou zero sessões TLS. As URLs de API, worker e
migrations não habilitam TLS. A porta foi publicada somente em loopback
(`127.0.0.1:25432`); os serviços também acessam o banco pela rede interna
Compose. **TLS para produção continua sendo requisito reservado ao ambiente
de produção/cloud; não foi habilitado nem alterado nesta execução local.**

**B5 resolvido para a candidata local `v1.0.0`.** A imagem operacional agora
está na série e patch corrigidos para CVE-2025-12817; digest e versão foram
confirmados na imagem realmente executada. Os serviços, health checks,
migrations, fluxo da API, armazenamento, publicação/reenvio da outbox e teste
empacotado obrigatório passaram. Não foi demonstrada outra vulnerabilidade
aplicável ou incompatibilidade nesta atualização. Permanecem as limitações de
cobertura já descritas nas triagens de dependências e a necessidade de TLS na
implantação de produção/cloud.

Após a validação, foram removidos somente containers, rede e volumes nomeados
do projeto isolado `docpipe-b5-postgres-20261005`. As imagens oficiais
PostgreSQL e RabbitMQ puxadas, a imagem Azurite preexistente e a imagem
DocPipe candidata preexistente não são artefatos temporários do projeto e
permanecem no cache local. O container externo `docpipe-control-plane` foi
verificado ativo; não foi removido nem modificado.
