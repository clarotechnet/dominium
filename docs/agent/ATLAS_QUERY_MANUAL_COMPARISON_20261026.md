# Natal — comparação de geração manual e reconhecimento de FALHOU

## Publicação verificada09:11

Patch publicado em main e instalado no servidor:
`ceae3fd22bbbd953586ce72dbd4047e8b2fd46d5`.
SHA256 do pipeline implantado:
`6b0fd4dd8831d116ada242ec8fbd85cd7368db4ad7bb77b7194d8df6e673c7e5`.
Backup SQLite query_jobs.before-falhou-status-20261026-091000.sqlite3 e
backup do módulo em DescRelay-20261010/backups/falhou-status-20261026-091000.
Reiniciado somente relay, protegido pelo mutex do watchdog; Chrome preservado.
GETautenticado200, anônimo401, banco íntegro24 trabalhos/163.049 linhas;
QUERY/confront/reports200. Frontend não alterado, sem deploy Hostinger novo.

Prova real pós-instalação: evaluate_query retorna **failed** para276921180.
276921301 retorna complete, sem XLS válido anunciado na inspeção atual;
usuário mostrou linkapp-1 com404. Não confundir complete com download válido.
O arquivo bom enviado pelo usuário tem20.150 linhasNATAL e não foi importado
como se pertencesse a qualquer desses IDs.

Automação horária ativa atualizada para ler também os manuais por
AtlasQueryData/natal_manual_status_20261026.py (saída sanitizada em
natal_manual_status_current.json). Falta o primeiro ID bem-sucedido para
comparação do download no servidor. Não gerar novos IDs nesta observação.

## Evidências novas do usuário

ID manual276921180, log26/10/2026,08:58:39, America/Sao_Paulo:
atlasBatch03, falha de tarefa java.lang.NullPointerException. Trecho causal:
DAOFactory.getDAO:196 → getJDBCDAO → executarQueryRelEquipamento:623 →
gerarReletorioEquipamento:445. Isso comprova falha da geração dessa fila;
não identifica qual referência estava nula nem prova indisponibilidade do banco.
Não generalizar essa exceção para os demais IDs sem os respectivos logs.
Não copiar o log bruto para Git: contém identidade do operador.

Depois o usuário informou uma geração manual com anexo válido e outra,
276921301, com XLS404/app-1. O screenshot exibe os anexos de276921301 e não
identifica o primeiro ID bem-sucedido. Não deduzir ID a partir do nome de arquivo.

Arquivo recebido, validado localmente com parse_report existente:
- 15.795.317 bytes, HTML em arquivo.xls,20.150 registros, todos operaçãoNATAL.
- SHA256438065421e4ea8b4dc3bae9aa7fa24b150e5f69800e90447cbe44eb3c6036b84.
- 11 campos tratados pelo parser; nenhum dado de cliente publicado.
- É geração atual válida fornecida pelo usuário, ainda sem vínculo confirmado
  ao ID Atlas de origem. Não inserir como resultado de outro ID nem declarar
  geração automática Natal aprovada.

Próximo dado necessário: primeiro ID que entregou esse XLS. Consultar o ID
real pelo conector e conferir hash/download no servidor, filtros/cidade e
processador. Uma geração funciona e outra falha; não reduzir o diagnóstico
a app-1/app-2, pois atlasBatch03 também apresentou falha em276921180.

## Defeito confirmado no DOMINIUM e correção mínima

Consulta real pelo conector retornava processing para276921180. Inspeção do
NetTask confirmou linha RELATORIO_EQUIPAMENTOS com status **FALHOU**. O parser
reconhecia ERRO/CANCEL/FALHA, mas não a palavra FALHOU.

Alteração única: adicionar FALHOU ao tratamento terminalfailed já existente.
poll_report persiste failed/remote_queue_failed, preservando o ID e usando a
mensagem de erro já publicada na UI. Sem alterar geração, filtros, download,
schema, estoques, contratos, O.S. ou TOA. Não transforma os COMPLETO/404 dos
IDs automáticos em erro Java presumido.

Regressão exercita evaluate_query e poll_report com a linha real sanitizada:
RED processing!=failed; GREEN confirma failed persistido e ID preservado.
52 testes Python QUERY aprovados; gate914 testes Python,21skip, JavaScript,
Ruff/build/auditoria aprovados. Revisão independente sem achados;14 testes
pipeline aprovados pelo revisor. Publicação/instalação são registradas após
conferir a versão efetiva.

## Acompanhamento

Automação horária ativa do novo par276921081/276921083 permanece existente.
Incluir a consulta manual276921180 e276921301 e o primeiro ID quando informado;
somente leitura, sem criar novas filas. Não equiparar a prova da sessão à
disponibilidade do relatório. A meta quatro cidades continua aberta.
