# Ponte n8n → DOMINIUM

O arquivo `DOMINIUM_Ponte_Datalake_TOA.json` é importável no n8n e não contém
credenciais. Ele recebe itens do fluxo TOA, monta o contrato
`dominium.toa.datalake.v1` e publica o mesmo lote no painel principal e na TV.

Variáveis do processo n8n:

- `DOMINIUM_MAIN_INGEST_URL`: `http://IP_DO_PC_PRINCIPAL:8765/api/toa-datalake/ingest`
- `DOMINIUM_TV_INGEST_URL`: `http://IP_DO_PC_DA_TV:8765/api/toa-datalake/ingest`
- `DOMINIUM_INGEST_TOKEN`: segredo longo e aleatório, igual nos dois receptores

Nos PCs do DOMINIUM, defina `DOMINIUM_INGEST_TOKEN` e inicie com
`python app.py --host 0.0.0.0 --no-browser`. Libere a porta apenas para a origem
do n8n/rede privada. Um n8n hospedado na internet não alcança endereços privados
sem VPN, túnel autenticado ou agente local.

Conecte o fluxo geral à ponte depois da normalização das atividades e OS. Use
`POST /api/toa-datalake/detail-queue`, com o mesmo cabeçalho Bearer e o corpo
`{"limit":100}`, para alimentar o fluxo detalhado apenas com atividades novas ou
alteradas. Depois, envie o resultado no array `details`.

Campos de detalhe aceitos: `contract`, `activity_id`, `observation`, `orders`,
`installed_equipment`, `removed_equipment`, `customer_equipment`, `materials`.
