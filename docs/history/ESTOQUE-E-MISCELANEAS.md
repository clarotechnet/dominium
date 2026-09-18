# Estoque e miscelaneas

Este arquivo registra o que foi confirmado no cliente oficial do Imperium e nas
capturas DataSnap. Ele deve ser a referencia dos proximos recursos de estoque.

## Conceitos

- Equipamento serializado: decoder, EMTA, Smart e outros itens controlados por
  serial. Uma OS pode instalar e remover varios equipamentos no mesmo fechamento.
- Smart: item separado do decoder. Somente alguns decoders antigos o utilizam.
- Miscelanea: material consumido na execucao da OS, como cabos, conectores,
  fixadores, aneis de vedacao e itens semelhantes.
- Estoque do tecnico: saldo principal usado na baixa da OS.
- Estoque da empresa: pode completar a quantidade quando o saldo do tecnico e
  insuficiente, conforme a regra do cliente oficial.
- Equipamento serializado em outro tecnico: exige transferencia de estoque antes
  da baixa. Nao e equivalente ao complemento automatico de miscelanea.

## Regras confirmadas

- Codigo 409 permite equipamentos instalados e, em trocas, removidos.
- Codigo 430 permite somente equipamentos removidos.
- `ADESAO DE ASSINATURA` nao recebe equipamento ou miscelanea; somente observacao.
- Uma linha de equipamento representa um serial e um tipo independente.
- Serial alfanumerico normalmente identifica EMTA. Serial somente numerico pode
  ser Decoder ou Smart e, por isso, continua com selecao manual no painel.
- Modelo padrao de decoder removido: `41001272`,
  `DECODER DIG. HD DCR7121 - PACE`.
- Modelo padrao de EMTA removida: `41001352`,
  `EMTA WIFI 2.0 DOCSIS SVG1202`.
- Modelo padrao de Smart removido: `41001234`,
  `SMART CARD AVULSO PRETO NOVO`.

## Colagem TOA

- Materiais TOA usam `invtype=106` e o codigo de material vem na propriedade
  `192`.
- Equipamentos serializados observados usam `invtype=6`; o tipo legivel vem de
  `_identifier_structure.invtype.text` e o serial vem de `invsn`.
- `inv_pid` identifica o responsavel do inventario, `inv_aid` a atividade e
  `335` o ponto da atividade.
- A linha `ID do Equipamento` e cabecalho descartavel, nao um material.
- Verde: item localizado e quantidade disponivel no estoque do tecnico.
- Amarelo: item localizado, mas o saldo do tecnico e menor que o consumo.
- Vermelho: codigo nao correlacionado ou sem saldo local valido.
- A colagem completa pode conter equipamentos destinados a OS diferentes da
  mesma atividade. O painel escolhe Decoder para servicos de streaming e EMTA
  para ponto Virtua, sem duplicar o conjunto de miscelaneas.
- Em `MUDANCA DE ENDERECO` com duas ou mais OS na mesma atividade, todas podem
  usar o codigo 409, mas somente uma OS recebe as miscelaneas. A fila
  semiautomatica agrupa as OS em uma unica tela por contrato, mostra o tipo real
  de cada OS e permite ao operador trocar a vinculacao antes da revisao; as
  demais ficam com zero miscelanea. Atividades TOA diferentes permanecem em
  grupos separados, mesmo quando pertencem ao mesmo contrato.
- Depois de uma baixa confirmada, a chave SHA-256 da colagem e a OS escolhida
  ficam em `logs/miscelaneas-toa-AAAAMMDD.json`. A mesma colagem ainda pode
  fornecer outro serial a outra OS, mas nao pode movimentar os materiais duas vezes.

## Datasets e providers confirmados

- `CdsMiscelanea`: materiais efetivamente associados a OS.
- `CdsColagemMateriaisTOA`: previa da colagem e validacao de saldo.
- `DspLocalizarEquipamentoDescricaoBaixaTOA`: correlacao do codigo/descricao TOA.
- Parametros da correlacao: `@Contrato`, `@IdInst` e `@DescEquip`.
- Retorno da correlacao: `IdEquipamento`, `CodigoEquipamento`, `Equipamento`,
  `Qtd`, `IdEstoque`, `Unidade`, `IdUnidadeNegocio` e `Identificado`.
- `TDtmEquipamentos.LocalizarSmart`: localizacao especifica de Smart por serial.
- A OS informa `RequerEquipEnt`, `RequerEquipSai` e `RequerObs` no cabecalho do
  codigo de baixa. Essas flags devem substituir inferencias pelo nome do servico.
- `DspLocEquipDescricao`, em `TDtmOrdemServico.AS_GetRecords`, retorna
  o catalogo de miscelaneas e o saldo do estoque do instalador da OS.
- `DspSpTransfAutomaticaMiscelanea`, no mesmo metodo, completa automaticamente
  pelo estoque virtual `RETORNO` as miscelaneas cujo consumo supera o saldo do
  tecnico. `RETORNO` nao possui instalador associado e e diferente de
  `ZN PRINCIPAL`.
- O delta de `CdsMiscelanea` foi reconstruido e comparado byte a byte com 29
  linhas oficiais de tres baixas 409 diferentes.
- A transferencia automatica de falta de miscelanea foi validada apenas na base
  Natal/Parnamirim. Nas demais bases, falta de saldo e bloqueada por seguranca.

## Equipamento em outro tecnico

O serial instalado e procurado no estoque do instalador responsavel pela OS. Se
estiver em outro tecnico, a baixa deve falhar sem alterar o estoque. Exemplo
observado em 17/07/2026: o serial `241786020013` estava no estoque de HAWELLS
OLIVEIRA, mas a OS era de GABRIEL SENA.

Fluxo confirmado em 18/07/2026 no cliente oficial e no DOMINIUM:

1. Consultar o serial e identificar o estoque de origem.
2. Transferir o equipamento serializado do tecnico de origem para o instalador
   da OS.
3. Confirmar a nova posse do serial.
4. Executar a baixa 409 normalmente.

O DOMINIUM exige previa, confirmacao explicita e leitura dos dois estoques depois
da escrita. Um timeout nunca repete a transferencia automaticamente.

## Timeout no complemento de miscelaneas

- O provider `DspSpTransfAutomaticaMiscelanea` e uma escrita anterior ao
  `ApplyUpdates` da baixa.
- Antes da escrita, o painel localiza e consulta o estoque virtual `RETORNO` e
  bloqueia imediatamente
  qualquer codigo cujo saldo de origem nao cubra a falta do tecnico. Os demais
  codigos continuam elegiveis para complemento.
- Depois que essa escrita comeca, uma falha de conexao nao pode reiniciar o
  preparo completo da OS, pois isso repetiria uma movimentacao possivelmente
  aplicada.
- O painel aguarda ate 180 segundos e executa o complemento no maximo uma vez
  por tentativa de baixa.
- Depois de um timeout, o socket e descartado e os saldos sao consultados em uma
  conexao nova. Se todos aparecerem, a baixa continua sem repetir a transferencia.
  Caso contrario, a OS permanece em campo e nenhum `ApplyUpdates` e enviado.
- A origem e localizada pelo nome no dataset do Imperium, sem fixar o ID no
  codigo. Se `RETORNO` estiver ausente ou ambiguo, a baixa e bloqueada antes da
  transferencia.
  A linha sem saldo deve ser removida da baixa; as outras duas podem ser
  complementadas automaticamente.

## Correcao de estoque 400 com seriais

Captura oficial de Alex em 18/07/2026, arquivo
`imperium-20260718-163034-DESKTOP-S0ENBOO-Alex-Mais-de-uma.zip`, SHA-256
`34484242B1AFF44E4D36A7F618D0AD1ED9788ADD41E07D5E28539D2C20798703`:

- 17 baixas com codigo `400`, descricao `CORRECAO DE CADASTRO` e
  `IdCodigoBaixa 37`.
- Todas as movimentacoes serializadas apareceram em `SqlEquipEnt`, o lado
  `Equipamentos Removidos`: o equipamento entra no estoque do tecnico.
- Nenhuma linha apareceu em `SqlEquipSai` e nenhuma miscelanea foi enviada.
- Foram 18 seriais ao todo. Uma unica OS adicionou tres extensores
  `41001567 - TERMINAL EXTENSOR WIFI5 MESH AR2180T`; as demais adicionaram um
  serial cada.
- A captura inclui EMTA, decoder, Smart Card, extensor Mesh e Hard Disk, portanto
  o sentido da movimentacao e definido pelo dataset (`SqlEquipEnt`/`SqlEquipSai`),
  nao pelo formato numerico ou alfanumerico do serial.

### Divergencia causada pelo horario da importacao

As rotas de desconexao sofrem movimentacoes de tecnicos entre 07:40 e 08:40 e,
por isso, devem ser importadas a partir de 09:00. Uma importacao feita as 07:00
pode deixar a OS vinculada ao tecnico anterior enquanto o equipamento continua,
corretamente, no estoque do executor atual. Nesse caso a tratativa e atualizar ou
reimportar a OS. Nao se deve transferir o equipamento apenas para satisfazer uma
OS com rota desatualizada.

### Correcao do instalador

O comando futuro de mudanca de instalador deve ser sempre limitado ao contrato
da OS que originou a acao. Antes de confirmar, o painel deve listar a quantidade
e os numeros das OS do mesmo contrato que serao alteradas, junto com o tecnico
de origem e o de destino. Selecoes com contratos diferentes nunca podem ser
alteradas em conjunto. O protocolo oficial do menu `Mudar instalador` ainda deve
ser capturado e confirmado antes de habilitar essa escrita.

## Pendente de captura oficial

- Delta de observacao para `ADESAO DE ASSINATURA`.
- Miscelaneas em uma OS 409 que tambem remove equipamento.

Credenciais, cookies e tokens do TOA nao devem ser gravados neste projeto.
