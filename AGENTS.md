# Instruções para agentes de código

## Escopo

Estas instruções valem para todo o repositório `docpipe-ingestion`.
Instruções mais específicas em subdiretórios prevalecem apenas dentro do seu
respectivo escopo. Em caso de conflito com uma solicitação explícita do usuário,
a solicitação atual tem prioridade.

## Contexto do projeto

Este repositório contém o microserviço de ingestão do DocPipe. Ele foi criado a
partir de um template Python mínimo da Campos Lab e será evoluído de forma
incremental conforme o `docs/PLAN.md`.

O Ingestion é a fronteira de entrada do pipeline. Sua responsabilidade é
receber e validar documentos, armazenar o arquivo original, registrar os
metadados em seu próprio banco e publicar o evento inicial para o restante do
processamento assíncrono.

Não trate placeholders do template como decisões de arquitetura. Também não
implemente antecipadamente toda a arquitetura planejada. Antes de introduzir
frameworks, serviços externos, filas, bancos de dados ou uma nova estrutura de
pacotes, confirme que isso pertence à etapa solicitada do `docs/PLAN.md`.

## Fonte de verdade e ordem de leitura

Antes de alterar código:

1. leia este arquivo e o `README.md`;
2. leia `docs/REQUIREMENTS.md`, `docs/DESIGN.md` e `docs/PLAN.md`;
3. confirme qual etapa e qual tarefa do plano foram solicitadas;
4. inspecione o código, os testes e a configuração existentes;
5. não invente requisitos para preencher lacunas relevantes.

Em caso de conflito entre documentos, use esta prioridade:

1. solicitação atual do usuário;
2. `docs/REQUIREMENTS.md`;
3. `docs/DESIGN.md`;
4. `docs/PLAN.md`;
5. `README.md`.

Se o conflito afetar contrato público, persistência, segurança, infraestrutura
ou escopo do serviço, interrompa a implementação e apresente a divergência.

## Estado inicial do template

- O ambiente local usa Python `3.14.4`; o template aceitava Python `>=3.13`.
  O `pyproject.toml` atual exige Python `>=3.14`.
- Dependências e ambiente virtual são gerenciados com `uv`.
- `pytest`, `pytest-cov`, `ruff`, `taskipy` e `typos` são dependências de
  desenvolvimento.
- O Ruff limita linhas a 79 caracteres, usa aspas simples na formatação e
  verifica as famílias `I`, `F`, `E`, `W`, `PL` e `PT`.
- `main.py`, `docker-compose.yml` e `.dockerignore` começam vazios.
- `tests/` contém inicialmente apenas o marcador de pacote.
- O `pyproject.toml` ainda pode usar o nome `python-project-template` e o alvo
  de cobertura `python_project_template`; substitua-os quando o pacote da
  aplicação for criado na etapa apropriada.
- O README inicial do template deve ser substituído ou atualizado conforme a
  interface real do serviço for implementada.

Sempre verifique o estado atual do repositório. Esta seção descreve o ponto de
partida e pode deixar de refletir arquivos já evoluídos.

## Autonomia obrigatória dos microsserviços

Todos os microsserviços atuais e futuros do DocPipe devem ser desacoplados,
independentes e possuir utilidade própria. Aplique esta determinação em toda
implementação e revisão:

- mantenha responsabilidade de negócio delimitada, repositório, domínio,
  banco de dados, migrations, configuração, testes e CI próprios;
- permita executar a responsabilidade do serviço sem exigir outros
  microsserviços em execução;
- comunique serviços por contratos públicos e versionados, aceitando
  produtores ou consumidores autorizados e compatíveis, sem exigir uma
  implementação específica;
- não importe código interno, modelos ORM ou classes de domínio de outro
  serviço, nem acesse diretamente seu banco, tabelas ou filesystem interno;
- preserve evolução e implantação independentes, respeitando a
  compatibilidade dos contratos.

Banco, RabbitMQ e armazenamento são dependências legítimas de infraestrutura.
Não os torne opcionais apenas para caracterizar independência. Receber,
registrar e armazenar documentos é uma capacidade própria do Ingestion, sem
exigir Processing ou conclusão das etapas posteriores. Preserve a outbox,
as confirmações do broker e a entrega pelo menos uma vez.

A auditoria por inspeção estática não identificou necessidade de refatoração
para autonomia; ela não realizou validação operacional. Não apresente essa
conclusão como teste aprovado ou comprovação operacional. Consulte a decisão
em `docs/DESIGN.md`, seção 19, e os critérios do RNF-009 em
`docs/REQUIREMENTS.md`.

## Limites do serviço

- Mantenha o Ingestion responsável somente pelo recebimento, validação,
  armazenamento, metadados, consulta do estado de ingestão e publicação do
  evento inicial.
- Não implemente OCR, classificação, extração de dados, relatórios,
  notificações, interface web ou autenticação própria neste repositório.
- Não acesse diretamente bancos ou tabelas de outros microserviços.
- O banco deste serviço é privado ao Ingestion.
- A entrega da `v1.0.0` deve executar em ambiente local/portátil com Docker
  Compose, PostgreSQL como banco exclusivo do Ingestion, Azurite para blobs
  privados e RabbitMQ para mensageria, com API e worker separados.
- PostgreSQL será o único banco operacional suportado. O suporte já existe,
  mas defaults SQLite/local e a composição principal ainda devem ser ajustados
  na Etapa 9. Não apresente esse planejamento como implementação concluída.
- SQLite pode permanecer somente como recurso interno das fixtures existentes,
  selecionado explicitamente, sem substituir os testes PostgreSQL. Preserve
  o adaptador local e seus testes sem criar outro percurso obrigatório de
  release. Não adicione obrigação de suportar dois bancos em execução.
- Migração do schema não implica transferência de dados SQLite. Não presuma
  transferência nem apague bancos, volumes ou documentos existentes.
- Não versione documentos recebidos nem o arquivo do banco SQLite. Preserve no
  Git apenas os diretórios vazios necessários, quando aplicável.
- Não devolva o binário, URL pública ou credencial de armazenamento nos
  contratos desta versão.
- Integrações externas devem ficar atrás de interfaces ou adaptadores quando a
  etapa correspondente for implementada.
- Não adicione dependências, infraestrutura ou abstrações sem uma necessidade
  concreta na tarefa atual.

## Evolução incremental

- Implemente somente a etapa ou tarefa do `docs/PLAN.md` solicitada.
- Considere as tecnologias descritas no `docs/DESIGN.md` e no `README.md` como
  planejadas até que a etapa correspondente autorize sua adoção.
- Cada mudança deve ser pequena, verificável e deixar o repositório em estado
  executável quando isso for aplicável à etapa.
- Não antecipe recursos de etapas posteriores. As Etapas 1 a 8 estão
  registradas como concluídas; a Etapa 7 cobre a instrumentação e a 8, CI.
  A Etapa 9 conclui a implementação funcional, seus testes e documentação;
  a Etapa 10 valida o conjunto com dependências reais, corrige defeitos
  encontrados e encerra a `v1.0.0`, sem etapa adicional de conclusão.
- As Etapas 9 e 10 continuam pendentes. Inspeção estática, checks anteriores
  e atualização documental não comprovam seu aceite operacional.
- Kind e Kubernetes não fazem parte da `v1.0.0`. Não introduza AKS, Azure
  Container Registry nem qualquer recurso Azure nas Etapas 8 a 10.
- Integrações e implantação em serviços Azure pertencem ao backlog da
  `v1.1.0`; Azure Service Bus permanece uma decisão futura, não confirmada.
- Planeje carga e resiliência somente após a validação funcional no ambiente
  Azure com Blob Storage e PostgreSQL. Preserve scripts, workflows, relatórios
  e evidências históricos, sem exigir novos ensaios para fechar a `v1.0.0`.
- O adiamento experimental não elimina testes funcionais de falha e retomada
  previstos nos contratos, não reduz cobertura nem enfraquece a CI. Use tarefas
  concretas para reenvio de eventos, reinícios e diagnóstico de órfãos; não
  amplie esse escopo para campanhas de falhas ou metas de desempenho.
- Antes de modificar contratos HTTP, eventos, migrations ou configuração,
  explique o impacto e confirme que a mudança pertence ao escopo solicitado.
- Registre decisões arquiteturais relevantes no `docs/DESIGN.md` ou, quando fizer
  sentido, em um ADR solicitado pelo usuário.

## Organização do código

- Quando o pacote da aplicação for criado, use layout `src/` e o nome Python
  válido `docpipe_ingestion`.
- Mantenha `main.py` apenas como ponto de entrada fino; regras de negócio não
  devem ficar nele.
- Espelhe em `tests/` a organização dos módulos da aplicação quando isso
  facilitar a localização dos testes.
- Separe integrações externas da lógica de domínio e injete dependências para
  permitir testes sem rede nem serviços reais.
- Separe domínio, casos de uso e infraestrutura apenas quando existirem
  responsabilidades concretas; não crie camadas ou interfaces vazias.
- Use operações assíncronas apenas em I/O que efetivamente se beneficie delas.

## Dependências e ambiente

- Use `uv add <pacote>` para dependências de execução.
- Use `uv add --dev <pacote>` para dependências exclusivas de desenvolvimento.
- Não edite `uv.lock` manualmente.
- Versione `pyproject.toml` e `uv.lock` juntos quando as dependências mudarem.
- Não adicione uma dependência quando a biblioteca padrão resolver o caso com
  clareza semelhante.
- Não troque ferramentas já configuradas por alternativas equivalentes sem
  necessidade explícita.

## Implementação e estilo

- Siga a configuração do Ruff presente em `pyproject.toml`; não replique essas
  opções em ferramentas paralelas.
- Adicione anotações de tipo nas interfaces públicas e onde eliminem
  ambiguidade.
- Prefira funções pequenas, nomes orientados ao domínio e fluxo de controle
  explícito.
- Trate erros nas fronteiras da aplicação e preserve a causa original ao
  convertê-los em erros de domínio.
- Use UUIDs como identificadores públicos dos documentos e horários em UTC.
- Trate nomes de arquivos e metadados do cliente como dados não confiáveis.
- Nunca use o nome original diretamente como caminho ou chave de armazenamento.
- Resolva e valide todo caminho final para garantir que permaneça dentro de
  `dataset/documents/`.
- Não carregue arquivos grandes integralmente em memória; prefira streaming.
- Respostas de erro HTTP devem ser consistentes e não expor detalhes internos.

## Dados e mensageria

Estas regras passam a ser aplicáveis quando as etapas de persistência e
mensageria forem solicitadas:

- alterações de schema devem usar migrations Alembic validadas em PostgreSQL;
  preserve o histórico existente e crie revisões somente quando necessárias;
- documento e evento outbox devem ser registrados na mesma transação;
- eventos devem ser versionados e validados por schema;
- o envelope deve conter `event_id`, `event_type`, `event_version`,
  `occurred_at`, `correlation_id` e `document_id`;
- a publicação segue entrega pelo menos uma vez e deve tolerar repetição;
- consumidores podem receber o mesmo evento mais de uma vez;
- nunca descreva a solução como garantia de entrega exatamente uma vez;
- a estratégia de consistência deve seguir o transactional outbox definido no
  `docs/DESIGN.md`;
- quando SQLite for usado internamente nos testes, preserve suas proteções de
  chaves estrangeiras, timeout e WAL pertinentes; ele não comprova o
  comportamento PostgreSQL de transações, constraints ou locks.

## Segurança e privacidade

- Valide tipo permitido, tamanho e assinatura básica do arquivo; não confie
  somente na extensão ou no `Content-Type`.
- Normalize e valide os metadados fornecidos pelo cliente.
- Nunca registre conteúdo de documentos, credenciais, tokens, segredos ou dados
  pessoais desnecessários.
- O arquivo original deve permanecer privado.
- Use dados sintéticos ou anonimizados em testes e demonstrações.
- Métricas não devem usar `document_id`, nome de arquivo, usuário ou outro dado
  de alta cardinalidade como label.
- Mudanças que ampliem a exposição de dados exigem revisão explícita.
- Nunca inclua arquivos `.env`, segredos ou credenciais no repositório ou na
  imagem de container.

## Observabilidade

Quando a instrumentação correspondente fizer parte da etapa solicitada:

- use logs estruturados e propague `correlation_id` entre requisição,
  persistência e evento;
- permita distinguir falhas HTTP, de banco, de storage e de broker;
- meça latência, volume, tamanho, erros e tempo gasto nas dependências;
- não inclua conteúdo do documento em logs, métricas ou traces;
- mantenha labels de métricas com cardinalidade controlada.
- mantenha a instrumentação desacoplada do backend de coleta, armazenamento,
  consulta ou visualização;
- não atribua a este repositório a stack central de observabilidade. Sua
  avaliação pertence a um futuro repositório integrador ou de plataforma,
  ainda não implementado nem formalmente aprovado.

## Testes

- Toda alteração de comportamento deve incluir ou atualizar testes.
- Os testes unitários devem ser determinísticos e independentes de rede,
  relógio real e ordem de execução. Use dublês nas fronteiras externas nesses
  testes.
- Integrações devem usar recursos isolados e descartáveis. A validação
  integrada da Etapa 10 exige PostgreSQL, Azurite e RabbitMQ reais no Compose,
  API por HTTP e worker separado; não substitua essas integrações por mocks.
- Cubra o caminho feliz, falhas esperadas e casos-limite relevantes.
- Não reduza cobertura, enfraqueça asserções nem remova testes apenas para fazer
  a alteração passar.
- Antes de concluir, execute no mínimo o lint e os testes afetados. Execute a
  suíte completa quando o alvo de cobertura estiver configurado corretamente.

## Comandos de desenvolvimento

Use os comandos disponíveis no estado atual do projeto:

```bash
uv sync --locked
uv run task lint
uv run task format
uv run pytest
uv run typos
```

O comando `uv run task test` também executa lint e gera o relatório HTML de
cobertura. Enquanto o alvo de cobertura ainda apontar para o pacote do
template, use `uv run pytest` para validar os testes. Execute verificação de
tipos quando ela estiver configurada no projeto.

## Docker e infraestrutura local

- Preserve builds reproduzíveis usando `uv.lock` e `uv sync --locked`.
- Mantenha a imagem de execução enxuta, sem dependências de desenvolvimento e,
  quando definido no plano, executada por usuário não root.
- Só preencha `docker-compose.yml` quando houver serviços locais concretos para
  orquestrar na etapa atual.
- Nunca copie `.env`, segredos, caches ou artefatos de teste para a imagem.
- O Azurite pode ser usado localmente, quando autorizado pela Etapa 6, sem
  criação de recursos Azure externos.
- A `v1.0.0` deve ser completamente executável e reproduzível localmente, sem
  conta, assinatura ou recursos de cloud provider.
- Docker Compose é o ambiente de execução e validação funcional da `v1.0.0`,
  com PostgreSQL, Azurite e RabbitMQ. Kind, Kubernetes e experimentos de carga
  ou resiliência não integram seu fechamento.
- Considere o notebook de 8 GB, uma API, um worker e verificações sequenciais.
  Uma VM pode hospedar o mesmo Compose; isso não constitui integração Azure
  nem autoriza criar infraestrutura externa.
- O Azurite usa APIs compatíveis com Azure Blob Storage, mas não comprova
  implantação nem validação no Azure.
- Não crie ou altere infraestrutura externa, recursos Azure ou clusters sem
  solicitação explícita.

## Manutenção da documentação

- Atualize o README quando mudarem requisitos implementados, comandos,
  configuração, ponto de entrada ou forma de executar o serviço.
- Atualize `docs/DESIGN.md`, `docs/REQUIREMENTS.md` e `docs/PLAN.md` somente
  quando a mudança solicitada alterar decisões, requisitos ou planejamento.
- Documente variáveis de ambiente pelo nome e finalidade, sem valores secretos.
- Mantenha exemplos executáveis e coerentes com `pyproject.toml`, `uv.lock` e
  `Dockerfile`.
- Diferencie claramente funcionalidades implementadas de funcionalidades
  apenas planejadas.

## Disciplina de mudanças

- Preserve mudanças preexistentes e não reformate arquivos sem relação com a
  tarefa.
- Não faça commits, pushes, merges, releases nem alterações de infraestrutura
  externa sem pedido explícito.
- Não modifique contratos públicos ou requisitos silenciosamente.
- Se uma verificação não puder ser executada, informe o motivo e não afirme que
  ela passou.

## Entrega esperada do agente

Ao concluir uma tarefa, apresente:

1. resumo objetivo do que mudou;
2. arquivos principais alterados;
3. testes e verificações executados, com seus resultados;
4. riscos, limitações ou verificações pendentes;
5. próximo passo sugerido dentro do `docs/PLAN.md`, sem implementá-lo.
