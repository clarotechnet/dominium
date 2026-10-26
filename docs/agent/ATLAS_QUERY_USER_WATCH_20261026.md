# Natal — novos IDs e acompanhamento solicitado pelo usuário

## Atualização08:58

Usuário testou os dois anexos e relatou404 em app-2/app-1. Snapshot do worker
confirmou attachment_http_404 em276921081 e276921083, zero linhas em ambos.
Banco íntegro24 trabalhos/163.049 linhas; três rotas autenticadas200 e módulos
de runtime inalterados. Usuário tentará criar um ID manualmente: aguardar somente
o número para comparação, sem gerar mais filas. Não inferir esse ID pelo nome
de arquivo nem misturar com o Natal histórico.

Automação ChatGPT Acompanhar QUERY de Natal atualizada e reativada com sucesso,
is_enabled=true e RRULE:FREQ=HOURLY, timezoneAmerica/Sao_Paulo. Escopo confirmado:
276921081/276921083, sem novas gerações. Criada inicialmente para o primeiro
pedido, pausada durante a geração do novo par e redirecionada antes de encerrar
esta execução. API não forneceu next_run_time; não prometer horário exato.

## Pedido e gerações confirmadas

26/10/2026, America/Sao_Paulo. Após explicar a dificuldade de atendimento pela
Claro, o usuário pediu nova QUERY para teste e acompanhamento futuro. Depois
pediu explicitamente **mais dois IDs**. Autorização limitada a QUERYs/relatórios;
sem TOA, baixas ou outras alterações operacionais.

| Solicitação | ID Atlas | Job local | Confirmação aproximada |
| --- | --- | --- | --- |
| Primeiro pedido pela UI | 276920952 | 6acef3aa165c40c993c55df5c8a01a1b | 08:51:40 |
| Reserva automática desse pedido | 276921013 | 9640db61828743dcac7a5d68e8f42679 | 08:53:30 |
| Novo par explícito — principal | 276921081 | 7b7b7ac2707e4201b88fef8845c1775e | 08:55:44 |
| Novo par explícito — reserva | 276921083 | ec629fb48e714ab38995363920194002 | 08:55:46 |

O usuário confirmou404 no XLS anunciado de276920952/app-2. O worker também
registrou attachment_http_404. A reserva276921013 chegou a COMPLETO sem anexo
listado na observação08:54; não contar isso como resultado validado.

## Execução controlada do novo par

Usado o conector ChromeAtlas existente (open/inspect_parameters/submit_once),
sem modificar código de produção ou reiniciar Chrome. Geração dupla operacional
explícita com backup SQLite antes e manifesto durável. Dois slots
submission_uncertain persistidos antes das requisições; cada ID confirmado foi
salvo pelo save_queue existente. Root/child ligados por fallback_of e mesmo
operador original. fallback_enabled=0 em ambos: exatamente dois pedidos deste
lote; nenhuma terceira QUERY automática.

Manifesto privado: AtlasQueryData/natal_user_pair_20261026_0854.json,
status=two_ids_confirmed. Reexecução do script recusa novo envio quando o
manifesto já existe. Submissão incerta interrompe o lote sem retransmissão.
Essa geração manual em lote atende à nova ordem expressa do usuário, preserva
os IDs anteriores e não altera a política geral do botão DOMINIUM.

Backup íntegro:
`C:\DominiumRuntime\AtlasQueryData\backups\query_jobs.before-user-pair-20261026-085541.sqlite3`.
Backup anterior ao primeiro clique: before-user-natal-watch-20261026-085133.sqlite3.
Nenhuma credencial, URL privada ou cliente foi registrado neste documento.

Às08:56:20: novo principal276921081 attachment_wait, origem anunciada app-2,
sem falha de download registrada ainda; reserva276921083 processing. Não
declarar arquivo disponível só por haver ID ou COMPLETO. Sessão real comprovada
pelo watchdog às08:55:19; snapshot SQLite integrity_check=ok.

## Fluxo de observação

1. Worker privado do relay acompanha os trabalhos persistidos, consulta fila,
   baixa/interpreta quando disponível e preserva retries de leitura com backoff.
2. Watchdog Windows existente PT5M comprova sessão por consulta NetTask;
   não renova credencial e não gera QUERY.
3. Automação ChatGPT **Acompanhar QUERY de Natal**, de hora em hora,
   observa este novo par e notifica resultado validado ou nova intervenção
   indispensável. Não enviar notificações repetidas por404 sem alteração.
   A antiga automação Fortaleza está pausada e permanece assim.

Script diagnóstico somente leitura:
`C:\DominiumRuntime\AtlasQueryData\natal_user_pair_watch_20261026.py`.
Resultado sanitizado: natal_user_pair_watch_current.json. A tarefa não deve
executar generate_user_natal_pair_20261026_0854.py nem gerar novas filas.

Quando houver anexo válido, conferir fonte/parser/SQLite/tabela/CSV/XLSX e
recarga. Após validar e notificar o resultado, pausar a automação ChatGPT.
Fortaleza29.529, Recife55.749 e Mossoró892 permanecem aprovadas nos registros
anteriores; Natal histórico não vale como geração atual. Meta quatro cidades aberta.
