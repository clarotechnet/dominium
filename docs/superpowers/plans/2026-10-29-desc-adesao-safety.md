# DESC e Adesão — correções de segurança e retomada

> **For agentic workers:** executar com superpowers:executing-plans, com testes antes das alterações.

**Goal:** aplicar as regras já decididas na ADR-004 sem habilitar baixas gerais.

**Architecture:** preservar os executores existentes; corrigir a preparação oficial e o planejador DESC. Código do runtime separado dos módulos web, com fonte e hashes registrados. Não inventar protocolo de baixa sem equipamentos.

**Tech Stack:** Python/unittest, Node, DataSnap e cliente HTTP Imperium existente.

**Spec:** `docs/agent/memory/ADESAO_IMPERIUM_EVIDENCIAS_20261029.md`, ADR-004 e pedido vigente.

## Global Constraints

- DESC por grupo, técnico e bucket; DataSnap; sem miscelâneas.
- Adesão pela API oficial; assinatura e INST GPON - INST CABO somente código.
- Todos os materiais exigidos devem ter cobertura comprovada; nunca enviar parcial.
- Nenhum envio real nem reativação dos executores durante esta correção.
- Toda publicação exige testes, backup e conferência de conteúdo.

## Review Focus

- Mistura de códigos na mesma atividade não pode deslocar equipamentos entre códigos.
- Equipamento repetido entre tarefas do mesmo código deve movimentar uma vez.
- Conflito entre direção ou códigos deve bloquear.
- Falta em um material deve bloquear antes de transferir os demais.
- Exceção de assinatura não se aplica a toda instalação ou Adesão.

### Task 1: preparação oficial

**Files:** `official_close.py`, `imperium_api.py`, testes correspondentes.
**Interfaces:** `build_manual_official_plan` preserva assinatura; `prepare_official_materials` bloqueia qualquer falta não coberta.

- [x] Escrever e executar regressões para assinatura/GPON com itens e materiais parcialmente cobertos.
- [x] Aplicar bloqueios antes de qualquer transferência ou envio.
- [x] Executar testes oficiais, de materiais e do app.

### Task 2: distribuição DESC

**Files:** `adm_allocation.py`, `toa_adm_task_splitter.py`, `integrations/desc_runtime/`, testes.
**Interfaces:** `single_os_allocation` produz um dono de equipamentos por código; runner mantém bloqueio de múltiplas O.S. até homologar fechamento das demais sem itens.

- [x] Preservar fontes verificadas do servidor; adicionar regressões de códigos mistos e seriais compartilhados.
- [x] Corrigir validação e consumo da evidência completa no planejador.
- [x] Executar testes locais e no runtime isolado; não habilitar writes.

### Task 3: verificação e memória

**Files:** memória técnica e documentação do runtime.

- [x] Conferir GETs oficiais de estoque e RETORNO sem movimentação.
- [x] Executar quality gate; documentar limitações reais e diferenças de implantação.
- [x] Registrar memória, publicar fonte testada e aplicar somente correções verificadas com backup.

## Ledger

- Base: main 61ef6a1; clone novo isolado; branch fix/desc-adesao-safety-20261029.
- Baseline: 84 testes Imperium e 40 testes oficiais/materiais aprovados.
- Ruling: continuar a implementação já autorizada pela ADR-004 e pelo pedido vigente, preservando automações desligadas.
- Ruling: não criar fechamento DataSnap sem itens por inferência. O protocolo das O.S. restantes precisa de homologação; deixar bloqueio explícito.
- Ruling: o runtime legado não tem stock_catalog no cliente HTTP; testar cliente atual em staging sem sobrescrever o legado.

- Task 1: complete — regressões RED/GREEN; guarda de itens obrigatórios e código-only testada.
- Task 2: complete — parser, alocação e ramo de filho único testados; multiOS permanece bloqueado por protocolo não homologado.
- Task 3: implementation complete — oito arquivos instalados com backup/hash; 8765/PM2 recarregados, gerais desligadas e 106 ativo. Fontes e documentação acompanham o commit desta entrega.
- Ruling: a orientação posterior do usuário autoriza o lote 106 às 23h como exceção; nenhuma outra automação foi ativada.
- Ruling: a API de estoque oficial respondeu, mas transferência integral por HTTP e confirmação assíncrona completa continuam pendentes de homologação. Não inventar endpoints.
