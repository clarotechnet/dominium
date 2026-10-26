# Atlas: monitor de sessão instalado em 26/10/2026

Verificado até aproximadamente08:42, America/Sao_Paulo.
**Meta quatro cidades ainda aberta por Natal: anexo404 na origem.**

## Implementado, testado e publicado

Commit operacional do novo monitor: `5fa31327d3941c7755e9fbfdf9314db172d0908c`,
publicado em main e instalado no DESKTOP-K7J3E1N às08:37. O módulo novo
`atlas_query_health.py` reutiliza ChromeAtlas/evaluate_query, escolhe um ID já
confirmado via SQLite mode=ro e faz consulta real NetTask. Não gera QUERY,
não migra/grava banco e não reinicia o Chrome. Cada observação substitui a
anterior com timestamp e resultado sanitizado.

Estados: authenticated somente após resposta real de fila identificada;
login_required quando o conector detecta necessidade de autenticação;
unknown para timeout, resposta não confirmada, banco inválido ou monitor indisponível.
O monitor não baixa anexos, não declara ready e não renova SSO/captcha.

Foi preservada a tarefa `DOMINIUM - Browser Watchdog`, intervaloPT5M,
MultipleInstances=IgnoreNew. O instalador adiciona somente a chamada Atlas ao
script original, mantendo as observações anteriores. Nenhuma tarefa ChatGPT
foi criada. A execução automática abaixo é a tarefa Windows do servidor.

| Execução | Tipo | Resultado real |
| --- | --- | --- |
| 08:37:27–08:37:33 | tarefa existente acionada para teste | authenticated; fila276908572 complete |
| 08:40:01–08:40:08 | próxima execução automática | authenticated; fila276908572 complete |

Agendador: Ready, LastTaskResult0, próxima execução08:45. O resultado0 do
agendador apenas comprova execução; a prova de sessão é o JSON produzido.
Arquivo privado: BrowserHealth-20261022/atlas-service-health.json.

## Backups e versão efetiva

- Backup antes do patch: `C:\DominiumRuntime\BrowserHealth-20261022\backups\atlas-session-20261026-083726-707`.
- SHA256 módulo implantado, igual ao GitHub:
  `399c8f6ddfe3558ad6debc452ca7c07617f99148df037f619665b118fb431fde`.
- SHA256 watchdog após integração:
  `fb8c4aacde9605bce39b1d31074f3cdc5e218def2c75a75a369e6e4e110e6eaa`.
- Recuperação: restaurar browser_watchdog.py do backup para remover a chamada;
  não mudar tarefa ou sessão Chrome. O módulo novo pode permanecer sem chamada.
- Frontend e serviço QUERY continuam na versão operacionalc94984b, já aprovada;
  este commit não altera assets HTTP nem exige novo deploy Hostinger.
- Banco após instalação: integrity_check=ok,20 trabalhos,163.049 linhas.
  QUERY jobs/confront status/disconnection reports autenticados200. Dois hashes
  dos módulos QUERY publicados continuam iguais a c94984b.

## Testes e revisão

9 testes novos de saúde RED→GREEN;51 testes Python QUERY aprovados.
Gate completo aprovado:913 testes Python,21 ignorados; JavaScript/Ruff/build/
auditoria aprovados, QUALITY_GATE_OK. A primeira execução do gate encontrou
3 imports Selenium ausentes na instalação local; dependências declaradas
foram instaladas e o gate completo repetido com sucesso.

Fixture isolada Windows:6 verificações aprovadas — preservação do código
original, instalação idempotente, backups, fallback de importação que substitui
sucesso antigo, erro de sintaxe sem alterar runtime e marcadores invertidos.
Revisão independente concluída; único achado (marcadores invertidos podiam
simular instalação) reproduzido RED e corrigido GREEN. O login real não foi
derrubado para testar expiração; esse ramo foi exercitado nos testes simulados.

## Validação atual do DOMINIUM

Usuário renovou login DOMINIUM pelo navegador; sessão Atlas servidor separada.
UI real: Fortaleza276907771/29.529, Recife276907778/55.749 e
Mossoró276907784/892 mostraram100 linhas na primeira página, CSV/XLSX habilitados.
Verificações integrais de fonte/banco/arquivos dessas gerações estão no registro
ATLAS_QUERY_VERIFICATION_20261026.md; não foram repetidos seis downloads nesta
retomada, pois não houve alteração de parser/exportador/frontend.

Natal: Consultar fila mantém276908463/276908572 e erro404, exportações
desabilitadas. Após recarregar, IDs e erro continuaram persistidos. Nenhuma
QUERY nova foi gerada nesta retomada. Rechecagem direta da origem confirmou
COMPLETO em atlasBatch02/app-2 e atlasBatch01/app-1, XLS/HTML/ZIP404 e navegação
normal Chrome404. Sessão válida não equivale a relatório disponível.

## Bloqueio externo e ação exata

Acesso a logs e armazenamento interno Atlas/BatAtlas não está disponível.
É necessário o administrador da origem investigar esses dois IDs e tornar
um anexo íntegro disponível ou indicar uma geração operacional de Natal.
Pedido pronto em ATLAS_BATATLAS_NATAL_ESCALATION_20261026.md; nenhuma mensagem
externa foi enviada. Depois disso, validar Natal até parser/banco/tabela/
CSV/XLSX/recarga, sem contar o ready histórico como geração atual.
