# Relatórios nativos de OS — 11/11/2026

Nova aba **Operação > Relatórios de OS**, endereço `#relatorios-os`.
Período inicial: ontem. Seleção de uma cidade no topo, até 31 dias por arquivo.
Dois XLSX: Todos os serviços e Manutenção / Visita Técnica. Parceria NET (1),
status "%" em ambos; tipo "%" e "2", respectivamente. Não filtrar pelo texto
do serviço: manutenção também inclui preventiva e troca de equipamento.

A rota autenticada GET `/api/order-reports/export.xlsx` passa pela sessão
Hostinger, política compartilhada, Worker VPC e relay privado. Acesso de
administrador/controlador. Só prepara AS_GetRecords e consulta DspGetOs /
more_blob; nenhum AS_Execute, baixa ou escrita no Imperium/TOA.

As 42 colunas e a aba "Ordens de Serviço" seguem os XLSX enviados pelo operador.
Datas DBI, horários em milissegundos e timestamps são números com formato Excel.
Código de baixa numérico; memo segue o separador nativo " | ". Valores ausentes
permanecem vazios; fórmulas vindas de texto não são executadas.
Identificadores além de 15 dígitos e com zeros iniciais ficam como texto para
preservar o valor original. Isso corrige a perda de precisão observada em duas
OS longas do XLSX nativo Todos.

Validação Natal 10/11/2026: 889 OS Todos, 80 Manutenção, mesma distribuição de
status e cabeçalhos dos dois originais. Manutenção: igualdade nas 42 colunas.
Todos: igualdade em 41 colunas completas; diferença na coluna OS somente nos
identificadores longos preservados. Comparação por hashes de colunas fora do git;
nenhum XLSX/PCAP, cliente, credencial ou resposta de produção foi versionado.
HTTP privado de teste: 200, MIME e nomes corretos, 889/80 linhas, 42 colunas;
viewer 403. Testes Python, UI e ponte com fixtures sintéticas.

Rollout: instalar order_reports.py e midas_reader.py e atualizar apenas o
desc_review_relay.py no runtime complementar DescRelay-20261010, com backup e
reinício quando o relay estiver ocioso. Publicar Worker com a configuração
existente e Hostinger pelo deploy automático da main. Não reiniciar DominiumMain,
TOA nem alterar gates operacionais.

Gate geral Windows: 1089 testes, 21 skips, quatro erros já existentes na main:
três limpezas de SQLite temporário WinError32 em Atlas e um teste antigo de
versão fixa de backlog-analysis.js. Testes específicos e demais verificações
devem ser avaliados separadamente; não declarar o gate integral aprovado.
