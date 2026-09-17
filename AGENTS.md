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

- O ambiente local usa Python `3.14.4`; o projeto aceita Python `>=3.14`.
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

## Limites do serviço

- Mantenha o Ingestion responsável somente pelo recebimento, validação,
  armazenamento, metadados, consulta do estado de ingestão e publicação do
  evento inicial.
- Não implemente OCR, classificação, extração de dados, relatórios,
  notificações, interface web ou autenticação própria neste repositório.
- Não acesse diretamente bancos ou tabelas de outros microserviços.
- O banco deste serviço é privado ao Ingestion.
- Na primeira versão, use SQLite para os metadados e a outbox.
- Na primeira versão, armazene os arquivos em `dataset/documents/` por meio de
  uma abstração de storage local.
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
- Não antecipe adaptadores Azure, mensageria, observabilidade completa,
  Kubernetes ou testes de carga.
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

- alterações de schema devem usar migrations Alembic compatíveis com SQLite;
- documento e evento outbox devem ser registrados na mesma transação;
- eventos devem ser versionados e validados por schema;
- o envelope deve conter `event_id`, `event_type`, `event_version`,
  `occurred_at`, `correlation_id` e `document_id`;
- a publicação segue entrega pelo menos uma vez e deve tolerar repetição;
- consumidores podem receber o mesmo evento mais de uma vez;
- nunca descreva a solução como garantia de entrega exatamente uma vez;
- a estratégia de consistência deve seguir o transactional outbox definido no
  `docs/DESIGN.md`;
- configure o SQLite com chaves estrangeiras habilitadas, timeout de bloqueio e
  modo WAL quando os testes demonstrarem que ele é apropriado;
- não trate SQLite como solução para múltiplas réplicas em produção.

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

## Testes

- Toda alteração de comportamento deve incluir ou atualizar testes.
- Os testes devem ser determinísticos e independentes de rede, relógio real e
  ordem de execução.
- Use dublês nas fronteiras externas.
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
