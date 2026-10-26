# Atlas — quarto nó de anexos identificado nos vídeos

## Diagnóstico confirmado em26/10/2026

Usuário forneceu vídeos14-15-40(103,62s) e14-19-28(74,42s), além dosIDs
276938198failed,276938201app-1/404,276938266app-2/404 e276938313funcional.
Frames amostrados e eventos decisivos inspecionados em resolução original;
OCR auxiliar das transições. Vídeos originais não alterados nem publicados.

Primeiro vídeo mostra198falhou, depois201processando e acesso ao anexo com404
noapp-1 aos~88s. Segundo vídeo mostra313amarelo aos~40–57s, verde aos~59–60s,
anexos aos~67s e início/conclusão indicada na lista de downloads aos~69–71s.
O link visível no rodapé éAPP-4. O vídeo não mostra a planilha aberta.
Não atribuir sucesso a esperarverde isoladamente: primeirovídeo também falha.

## Defeito específico do conector

FILE_URL ematlas_query_pipeline.py aceitava somente/app-[123]//RELATORIOS/...
O endereçoapp-4oficial era descartado porvalid_report_url. Consulta real no
servidor antes do patch:313complete masattachment_urlvazio, emboraDOM da aba
Anexos tivesse o XLS anunciado emapp-4. Logo não era necessário trocarChrome
para acessar esse arquivo. Esse defeito é diferente dos anexos anunciados que
respondem404; a correção não prova resolução deapp-1/app-2.

Consulta atual dos outrosIDs confirmou198failed,201complete/404app-1 e
266complete/404app-2. Nenhuma nova QUERY submetida; Chrome não reiniciado.

## Fonte313 validada no próprio Chrome do servidor

Download do mesmo link oficial observado:HTTP200,15.746.227bytes,
SHA2567af9e8ecdc3fa9b240ea47ab329a39d6937b2a1f190be19c01511becfa66af17.
Parser existente retornou20.084registros,todosNATAL. Origem:user_manual_generation.
Arquivo privado:AtlasQueryData/manual_natal_276938313_source.xls.
Diagnósticos sanitizados:manual313_app4_download_current.json e
manual_comparison_276938313_current.json. Não foi inserido no banco como uma
QUERY automática nem substituído o histórico2051manual20145linhas.
Não foi confirmado hash do download doPC do usuário; não alegar igualdade
byteporbyte entre arquivos dos doisPCs. Apenas mesma fila e mesmo endereço.

## Correção e verificações

Alteração mínima:/app-[1234]//. OrigemHTTPSbatatlas continua exata, semcredenciais,
porta,query,fragmento,traversal. app5/app40 etc continuamnegados.
RegressõesURLapp4 e seleção doanexoapp4 apósprocessocomplete falharam antes
(RED) e passaram depois(GREEN);24 testes focadospassaram. Gate947Python,
21ignorados, suítesJS,Ruff,auditoria,contexto ebuild aprovados.

Publicado na main:e6170b9c896aaaa300f4ed08dfa9bb04c177d4f5 [skip deploy],
pois somente móduloPython/testes/índices; UIHostinger permanece2475433/asset3.
Instalado somentepipeline no relay commutex do watchdog ebackup de módulo/banco:
query_jobs.before-app4-20261026-142831.sqlite3,íntegro;27jobs183194linhas
preservados;GETautenticado200,anônimo401;somente relay reiniciado.
Hashpipeline6f12cce2e571194558f69e233647adaa7ca1cfd8ce18da595b21e528d1c5a98a.

## Limites e continuidade

Meta automáticaNatal seguependente até uma fila criada peloDOMINIUM entregar
fonte válida e validarSQLite/tabela/CSV/XLSX/recarga. O manual313 confirma o
quarto nó e sua leitura peloChrome, não comprova nova geração automática.
Parautomático276935365/276935412 não deve ser reenviado; worker fazbackoff.
Não associar313 a essesjobsnem atribuir seusdados a outroID.
Preservar relatóriosFortaleza276907771/29529,Recife276907778/55749,
Mossoró276907784/892 eNatalmanual276922051/20145. SemTOA/baixas/estoques/OS.

Verificação pós-instalação inicial de evaluate_query313 sofreu timeout deCDP
antes da leitura dos anexos; foi iniciada uma reconsulta somenteleitura. Não
interpretar timeout de leitura como nova falha de geração ou autorizar reenvio.

A reconsulta pós-instalação também retornouWebSocketTimeoutException. Verificado
no processo instalado:valid_report_url aceita endereçoapp4 observado ehashpipeline
confere;SQLiteíntegro e nenhumjobattachment_missinglegado para recuperar.
DownloadHTTP200/parser313 ocorreram no mesmoChrome antes deinstalaropatch,
comGETdiagnóstico exato. Não alegar evaluate_query completo pós-instalação
aprovado nem loginexpirado:timeoutnão provaautenticação. Semnovo envio.
