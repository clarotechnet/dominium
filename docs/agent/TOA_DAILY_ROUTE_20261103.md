# DOMINIUM — rotas diárias TOA e tratativa de improdutivas (03/11/2026)

## Regra operacional homologada com usuário
- **Pendente** no TOA = O.S. não iniciada, ainda sem código de baixa; não é improdutiva.
- **Em rota / iniciada** = trabalho em andamento; não é improdutiva.
- **Concluída** + código confirmado 101, 106, 306 ou 404 = **improdutiva confirmada**.
- **Concluída** + 409, 430 ou 512 = **produtiva confirmada**.
- Concluída com outro código = **baixada, validar código**. Sem código = **concluída sem código**.
- Pendente/suspensa com código preenchido = **divergência**, sem presumir que houve baixa.
- As classificações são apenas leitura da rota do TOA; NENHUMA baixa, escrita no Imperium ou envio de WhatsApp é feita.

## Fluxo implementado
1. Usuário operacional autorizado clica **Buscar 5 rotas do TOA** no DOMINIUM.
2. Web usa **POST /api/backlog/year/routes** com {`"source":"toa"`}; CSRF, role admin/controller e Worker VPC existentes são preservados.
3. Sidecar localhost exporta por **GET /toa/buckets** e **GET /toa/export** usando o helper já existente `toa_secondary_bucket_export.mjs` da sessão TOA.
4. Buckets fixos: `NTL-DMV_ADM`, `PWM-DMV_ADM`, `FTZ-DMV_ADM`, `JCR-DMV_ADM`, `MRO-DMV`.
5. **Só depois de obter e validar os cinco arquivos**, substitui atomicamente `route_rows` / `route_batches`; histórico anual `history` permanece intacto.
6. **GET /api/backlog/year/status** agrega `toa_import` e `daily_treatment` para o painel; não se criam novos endpoints públicos.
7. O agendamento DataSnap das **22h permanece independente** e inclui o próprio dia; o comparador de histórico existente e o upload manual continuam disponíveis.

## Evidência operacional (03/11/2026)
- Servidor `DESKTOP-K7J3E1N`, sidecar local `127.0.0.1:9342`.
- Captura real das cinco rotas concluída: **388 atividades** (Natal 135, Parnamirim 22, Fortaleza 114, Mossoró 34, Recife 83).
- Com códigos validados no TOA: **104 improdutivas**, 62 produtivas; 176 pendentes; restantes separados por status/código. Esses valores são um snapshot, não totais definitivos.
- SQLite verificado `ok`, 101.703 linhas de histórico preservadas.
- Testes: 42 Python `test_backlog*.py` no PC de trabalho; 32 testes no Python do servidor antes da ativação inicial; smoke autenticado da nova API HTTP 200 após reinício.
- Backups: `C:\DominiumRuntime\BacklogLab-20261030\backups\20261103-route-toa-before` e `...\20261103-existing-endpoint-before`.
- Falha inicial de ativação causada por smoke legado que exigia exatamente 1 linha em `route_rows`; corrigido para conferir preservação sem número fixo. Reinício seguinte passou.
- A captura direta TOA é **sob demanda no painel**, ainda não é rotina automática diária. A atualização do histórico DataSnap segue agendada às 22h.
- A interface web deve ser publicada da branch origin/main atual, preservando funcionalidades recentes; a branch de backend não substitui o front-end mais recente.

## Regressões a preservar
- Nada invoca `POST` do Imperium, fechamento de O.S. ou alteração de estoque.
- A importação manual continua possível; não aceitar nomes/caminhos arbitrários.
- Impedir sobreposição com carga de histórico e atividade operacional, respeitando `OperationalReadGate`.
- Não substituir dados da rota se qualquer uma das cinco exportações falhar.
- Os tokens do relay e as planilhas privadas permanecem fora do repositório.
