# Recursos / Consultar Seriais — historico DataSnap

## Protocolo real

Implementado a partir de captura do IMPERIUM Natal (porta DataSnap 212), sem armazenar a captura nem seriais reais no Git. A sessao privada inicia com prepare("TDtmMovEstoque.AS_GetRecords") e usa o novo handle na requisicao execute. As duas consultas MIDAS sao DspConSerial (movimentos) e DspConCaixaSerial (caixa), com Tipo A (Analitico) e Tipo S (Sintetico).

O codigo contem templates sanitizados sem o serial capturado. As consultas diretas sao aceitas para seriais de 12 caracteres alfanumericos. Em 22/10/2026, confirmamos as respostas MIDAS nos modos Analitico e Sintetico usando serial ficticio nas portas DataSnap de Natal/Parnamirim (212), Fortaleza (596), Mossoro (579) e Recife (599). Isso verifica a compatibilidade do protocolo, mas nao substitui a validacao posterior de historico com seriais reais em cada cidade. A consulta nao deve afirmar ausencia de equipamentos quando nao encontra movimentacoes.

## Componentes

- midas_reader.py: decodificador binario MIDAS limitado a 4 MB, 128 colunas e 5000 registros; tipos de texto, inteiros e data Delphi.
- serial_datasnap.py: conexao DataSnap read-only, prepara o handle dinamicamente, preenche query com serial, executa movimento e caixa e valida respostas.
- serial_service.py: valida GET, 1–20 seriais, Analitico/Sintetico, consulta a base local historica (SQLite somente leitura), compoe o JSON. Distingue ultimo destino e posse atual confirmada. Consulta de posse apenas quando destino tem estoque valido; nunca indica proprietario confirmado sem conferir stock serial de fato.
- desc_review_relay.py: base do relay DESC /8793 atualizada com a rota read-only, preserva DESC e estoque oficial.
- Hostinger: policy libera apenas GET /api/serials/consult para sessao autenticada, Worker aplica restricao admin/controller, sem cookies do browser.
- UI: Recursos → Consultar Seriais, selecao Analitico/Sintetico, ate 20 seriais, historico DataSnap e historico local, exportacao CSV.

## Publicacao e seguranca

Backups do relay na pasta C:\DominiumRuntime\DescRelay-20261010.
Publicar primeiro o relay local, depois o Worker do Cloudflare, e por ultimo GitHub Actions → Hostinger. Workflow valida consulta sintetica ZZZZZZZZZZZZ em todas as quatro conexoes operacionais e nos dois modos antes do upload. Parnamirim usa a conexao Natal.
Nao publicar PCAP, serial real, credenciais, token, ou dumps de dados de clientes. Nenhuma baixa/transferencia executada.
Rollback: restaurar relay anterior, depois versao anterior do Worker e commit anterior Hostinger, se necessario.
