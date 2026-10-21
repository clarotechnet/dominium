# DESC — contratos, revisão manual e REPORT

## O que muda

1. O frontend agrupa VISUALMENTE lotes do mesmo contrato, técnico (sender), grupo WhatsApp e praça numa caixa, mantendo todas as fotos (inclusive quando chegaram em lotes separados). Em grupos com mais de um lote, cada lote continua selecionável e as ações operacionais se aplicam apenas ao lote selecionado. Não mistura materiais ou aprova automaticamente.
2. O botão **Revisão manual** chama o POST existente `/api/disconnection/manual`, para criar uma revisão com grupo, técnico, contrato e seriais opcionais. O Bot DESC atual declara `mode:test` e sempre grava `simulated`, nunca baixa O.S. de verdade. Não mudar este comportamento sem executor validado, evidências e confirmação independente.
3. O **REPORT** tem diálogo de erro/melhoria/sugestão, prioridade, título e descrição; persiste cada registro com ator/data/área/contrato no TECHNET e permite reabrir os últimos 50 relatórios. Mantém somente diagnósticos resumidos, saneados, capturados na interface; não envia cookies, Authorization nem logs brutos.

## Fluxo privado

DOMINIUM autentica papel admin/controller e verifica CSRF. A rota `GET/POST /api/disconnection/reports` passa pelo disconnection-proxy.js, Worker `dominium-import-bridge` e VPC DESC_SERVICE até o relay `127.0.0.1:8793`. O relay revalida token e papel. `operator_reports.py` grava JSONL persistente em:

`C:\DominiumRuntime\DescRelay-20261010\state\operator-reports.jsonl`

Não apagar o arquivo em reinstalações, releases ou backups. Cada entrada recebe UUID, data UTC, operador, categoria, severidade e status `recebido`. São aceitos somente tipos pré-definidos, tamanho limitado, até 20 relatórios/hora por operador. Trechos parecidos com senhas/tokens são mascarados. Retenção/gestão avançada posterior.

## Rollback

Antes de atualizar o serviço, copiar `desc_review_relay.py` como `desc_review_relay.pre_reports_20261021.py` e guardar o arquivo. Instalar somente `operator_reports.py` e o novo `desc_review_relay.py`; reiniciar somente a porta 8793 com `ensure-desc-relay.ps1`, sem tocar em 8765/8791. Worker usa a versão anterior registrada no Wrangler como fallback. Hostinger volta via GitHub Actions a partir do commit anterior, preservando o segredo privado.

## Testes

- `python -m unittest tests.test_desc_operator_reports`
- `node --test tests/test_disconnection_frontend.js integrations/import_bridge/worker.test.mjs tests/test_disconnection_hostinger.js`
- `python scripts/quality_gate.py`
- Teste local isolado na porta 8796: GET anônimo 401, viewer 403, operador 200; POST operador 201 e histórico GET, sem registros de teste na produção.
- Teste em produção apenas de leitura (GET relatórios) no preflight GitHub, antes de subir pacote à Hostinger.
