# Relatórios de Comissão – Imperium DataSnap (12/11/2026)

## Escopo

- Novo menu **Operação → Relatórios de Comissão**, abaixo de Relatórios de OS.
- Fonte única: DataSnap do Imperium, método TDtmComissionamentoServicos.AS_GetRecords, somente leitura.
- Bases: Natal/Parnamirim (212), Fortaleza (596), Mossoró (579) e Recife/JCR (599).
- A API HTTP de comissão do Matheus atende somente Natal; não foi usada nem publicada.
- Período máximo por download: 31 dias. DataIni e DataFim têm formato UTF-16LE e substituição estrita.
- DspListaInstaladores → aba Comiss.Sintético, seis colunas.
- DspComissInstSint → aba Comiss.Analítico, nove colunas.
- DspContratosComissInst → aba Contratos, dez colunas.
- As consultas usam prepare, execute e, quando necessário, more_blob no índice 2.
- O protocolo foi capturado pelo gravador v1.1.0. PCAPNG, credenciais e dados de clientes não foram versionados.

## Validação real (01/11 a 11/11/2026)

| Base | Sintético | Analítico | Contratos |
| --- | ---: | ---: | ---: |
| Natal/Parnamirim | 87 | 420 | 2625 |
| Fortaleza | 53 | 272 | 1440 |
| Mossoró | 6 | 36 | 158 |
| Recife/JCR | 43 | 218 | 796 |

As 12 contagens conferiram com as planilhas do operador. Os retornos MIDAS maiores que 63.488 bytes foram reconstruídos usando more_blob. Quatro XLSX de três abas foram gerados em memória e tiveram linhas e XML validados. A consulta de um único dia (Mossoró, 10/11) devolveu 4, 10 e 13 registros, validando a alteração das datas.

## Arquitetura e controles

Hostinger (sessão DOMINIUM, admin/controller) → Worker Cloudflare (allowlist GET) → DESC Relay autenticado 8793 → DataSnap.

- Cidade única por consulta, com bloqueio de exportação ao selecionar Todos.
- Credenciais existentes permanecem somente no servidor.
- Respostas incompletas ou inválidas não geram arquivo.
- Uma consulta por cidade de cada vez.
- MIME XLSX, cache no-store e nome de arquivo fixado pelo servidor.
- Relatórios de OS e rotinas de baixas não foram alterados.
- Publicação: relay local, Worker Cloudflare e por último Hostinger. Exige HTTP 200 + ZIP íntegro.

## Testes

- tests/test_commission_reports.py
- tests/test_commission_reports_ui.cjs
- integrations/import_bridge/commission_reports.test.mjs
- Regressões tests/test_order_reports.py e tests/test_order_reports_ui.cjs.
- Consultas reais em quatro bases sem qualquer método de escrita.
