# Histórico DESC — carga XLSX e atualização diária (03/11/2026)

## Escopo

- Fonte inicial: exportações Imperium de TODOS / DESCONEXÃO para NTL, MRO, FTZ e JCR.
- Importação em SQLite via backlog_seed_xlsx.py, preservando a linha do export e a projeção para o BacklogHistoryService.
- Nome de cliente, endereço, observações livres e telefones NÃO são persistidos nesta carga.
- O.S. com identificadores compostos ou em notação científica são preservadas com verificação `xlsx_seed_ambiguous_os`, sem gerar número fictício. Oito linhas com contrato inválido permanecem em history_seed_rejections (somente arquivo/aba/linha/motivo).
- Arquivos repetidos são reconhecidos pelo SHA-256. Checkpoint avança só após importação completa.

## Carga dos quatro arquivos de 03/11/2026

| Perfil | Importados | Rejeitados | Intervalo |
|---|---:|---:|---|
| natal | 56.051 | 4 | 03/11/2025 a 31/10/2026 |
| mossoro | 3.353 | 2 | 03/11/2025 a 31/10/2026 |
| fortaleza | 32.985 | 1 | 03/11/2025 a 31/10/2026 |
| recife | 9.314 | 1 | 05/02/2026 a 31/10/2026 |
| **Total** | **101.703** | **8** | |

Recife possui cobertura incompleta: janeiro/2026 e parte do período anterior não constam do arquivo. Checkpoint não comprova cobertura anterior.

## Atualização via DataSnap

- O dataset principal consulta status=all e service_type=disconnection.
- As quatro leituras auxiliares de status usam igualmente disconnection.
- Códigos de baixa são lidos no detalhe; nunca inferidos pelo status.
- Agendador diário inicia às 22h UTC−03:00 (verificação periódica até 22:44); uma tentativa por data. Inclui a data corrente do dia da execução.
- A coleta das 22h inclui o dia corrente, e até 7 dias pendentes por base podem ser recuperados.
- Em 03/11, a rotina recupera 01/11 e 02/11 e captura 03/11 a partir das 22h.
- Falha ou interrupção não avança o checkpoint do dia incompleto; a próxima execução retoma.
- OperationalReadGate bloqueia leitura durante execução de baixas operacionais.
- Nenhum método de escrita do Imperium, estoque ou TOA faz parte da rotina.

## Operação e rollback

Importar as planilhas no banco de dados do sidecar, após backup:
python backlog_seed_xlsx.py --db CAMINHO_DB NTL.xlsx MRO.xlsx FTZ.xlsx JCR.xlsx

Ativar via argumento --daily-sync no backlog_sidecar.py somente após smoke tests. Sem esse argumento o agendador permanece inativo.

Rollback: interromper o sidecar de backlog, restaurar código original sem --daily-sync e banco a partir do backup pré-carga. Não restaurar o projeto Imperium/TOA por esta mudança.

## Testes

python -m unittest discover -s tests -p test_backlog_seed_daily.py
python -m unittest discover -s tests -p test_backlog_imperium_service.py

A primeira execução real das 22h somente será confirmada pelo log `sync_runs` e checkpoints após a janela de 03/11/2026. Testes unitários, HTTP e DataSnap de leitura não provam por si a execução agendada.
