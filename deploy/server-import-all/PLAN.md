# Importação de todos os buckets DMV

Pedido: importar os 13 buckets das cinco praças, incluindo adesão, para preparar um teste de baixa produtiva.

Implementação: manter as regras DESC intactas e criar um caminho separado de exportação/importação geral. Usar a sessão gerenciada existente, apenas dados do dia, a validação vigente de cidade/perfil e a reconciliação de O.S. já presentes no Imperium. Não ampliar códigos de baixa automática nem executar baixa de adesão nesta importação.

- [x] Conferir o runtime efetivo e os filtros nas quatro camadas.
- [x] Testar inclusão de adesão e 13 buckets, exclusões de data/identidade/duplicidade e preservação do escopo DESC.
- [x] Validar o patch contra as fontes efetivas, sintaxe e comportamento do agendador/ponte.
- [x] Fazer backup dos arquivos alterados e do estado do agendador. Preservar Chrome e demais serviços.
- [x] Instalar, reiniciar somente painel/ponte quando ocioso e verificar hashes e APIs.
- [x] Executar uma rodada de importação e conferir resultados individuais dos 13 buckets no backend.
- [x] Localizar uma O.S. de adesão importada para o próximo teste, sem executar baixa em lote.

Rodada 09:53:24–10:03:26: 799 importadas, 427 existentes/reconciliadas, 38 sem confirmação,
67 excluídas pelas validações. As pendências não foram reenviadas. O script reutilizável
de instalação exige painel/gateway e supervisores offline; não encerra processos online.

O instalador falha antes de escrever se qualquer âncora de fonte mudou. O backup permite restaurar os arquivos anteriores. Os CSVs, dados operacionais e credenciais permanecem fora do repositório.
