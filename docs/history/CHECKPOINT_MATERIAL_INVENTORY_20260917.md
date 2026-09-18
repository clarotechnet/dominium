# Checkpoint — material inventory

Data: 2026-09-17

Corrigido erro `list object has no attribute strip` em GET `/api/orders/{id}/material-inventory`.
Causa: fallback de query string criava lista aninhada quando login/name nao eram enviados.

Caso real validado:
- OS 2656834282 / IdOS 2207229
- instalador: VICTOR AMARAL
- inventario retornado: 83 itens
- 22024800: tecnico 8 / RETORNO 11
- 22025321: tecnico 0 / RETORNO 9

Teste de regressao adicionado em `test_app.py`.
Suite relacionada final: 136 testes OK.
Backup: `backups/material_inventory_query_20260917`.
