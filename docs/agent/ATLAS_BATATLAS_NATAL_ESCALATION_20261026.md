# Natal: anexos de relatório indisponíveis no Atlas/BatAtlas

## Solicitação técnica pronta para o administrador da origem

Investigar a entrega dos relatórios de equipamentos de Natal, localização
EMPREITEIRA. A solicitação por
`NetHomeEquipamentoService.relatorioEquipamentosAnaliticoExportacaoTaskV2`
recebeu IDs confirmados e a fila terminou como COMPLETO, mas os documentos
anunciados não podem ser obtidos pelo Chrome autenticado.

| ID | Solicitação (26/10, America/Sao_Paulo) | Processador anunciado | Publicação anunciada | GET XLS/HTML/ZIP |
| --- | --- | --- | --- | --- |
| 276908463 | 00:51:37 | atlasBatch02 | app-2 | 404/404/404 |
| 276908572 | 00:53:04 | atlasBatch01 | app-1 | 404/404/404 |

Rechecagem em 26/10, aproximadamente 08:25: mesmo resultado; navegação normal
do Chrome para cada XLS também respondeu404/text-html. NetTask respondeu à
consulta real. Não é apenas estado visual de uma guia aberta. O monitor real
de sessão confirmou novamente leitura autenticada do ID276908572 às08:37:33.

## Verificações necessárias na origem

1. Correlacionar os dois IDs com logs da geração e da conclusão do processo.
2. Conferir se cada artefato foi gravado, seu tamanho e o caminho efetivo.
3. Correlacionar esse caminho com o link anunciado pelo NetTask/BatAtlas e
   verificar acesso, montagem/replicação e publicação nos nós correspondentes.
   São pontos a investigar, não causas já provadas pelo DOMINIUM.
4. Informar por que COMPLETO foi emitido sem um documento acessível ou
   disponibilizar/reprocessar somente os relatórios autorizados desses IDs.
5. Confirmar pelo mesmo perfil autorizado que ao menos um formato íntegro
   pode ser baixado. Informar a forma oficial de geração caso este relatório
   tenha mudado de serviço ou regra para Natal.

## Evidência comparativa e limite

Fortaleza276907735 também anunciou documento404 em app-1, enquanto a reserva
276907771 entregou arquivos200 em app-3 e29.529 registros válidos. Recife276907778
e Mossoró276907784 entregaram relatórios válidos em app-3. Essa associação entre
nó e disponibilidade não basta para afirmar uma causa interna. O Natal histórico
276868277 foi preservado, mas não comprova a geração atual.

O conector DOMINIUM não fornece acesso ao armazenamento/logs internos da origem.
Não há acesso administrativo Atlas/BatAtlas disponível nas ferramentas atuais.
Este texto está preparado para encaminhamento; nenhuma mensagem foi enviada.
Não contém credenciais, cookies, links privados de documentos ou clientes.

## Critério de encerramento

Após a disponibilização, repetir download nativo se necessário, parser,
comparação com SQLite, tabela, CSV/XLSX íntegros e recarga da página em Natal.
Preservar rastreabilidade dos IDs. A meta das quatro cidades permanece aberta.
