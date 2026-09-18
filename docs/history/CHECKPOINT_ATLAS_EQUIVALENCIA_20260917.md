# CHECKPOINT - Descricao Atlas / equivalencia de miscelaneas

Data: 2026-09-17
DOMINIUM: primario (DESKTOP-R285TSA)

## Problema corrigido
A OS 2656936937 era retida porque o codigo 22025321 nao era reconhecido pela preparacao de miscelaneas, apesar de existir na Descricao Atlas do Imperium.

O DspLoc real retorna para 22025321:
- Grupo derivado: ANEL VEDACAO
- 22025321 - ANEL VEDACAO PLASTICA P PORTA F
- 22056757 - ANEL VEDACAO PLAST. P/ PORTA F

## Causa
O layout real do registro DspLoc traz ATIVO no campo anterior ao ultimo flag. O parser esperava ATIVO sempre no ultimo campo e descartava o registro.
## Comportamento novo
A baixa procura primeiro o codigo solicitado. Se o saldo exato nao for suficiente, consulta o grupo oficial da Descricao Atlas e consome os codigos equivalentes em sequencia ate completar a quantidade.

Para o caso validado:
1. tenta 22025321;
2. se faltar, usa 22056757;
3. so retém para tratativa humana se o grupo inteiro nao cobrir a quantidade.

Nao ha substituicao por semelhanca textual: apenas codigos pertencentes ao mesmo grupo Atlas oficial sao aceitos.

## Validacao
- consulta DspLoc real de 22025321: OK
- parser retornando 22025321 + 22056757: OK
- testes novos de regressao: OK
- suite final: 135 testes OK
- git diff --check dos arquivos alterados: OK

Backup anterior a correcao: backups\atlas_parser_20260917

## Confirmacao por captura Imperium 16:15-16:17
- PCAP enviado pelo operador confirmou consulta DspLoc e os campos de Descricao Atlas.
- Para 22025321, a resposta real contem:
  - 22025321_ANEL VEDACAO PLASTICA P PORTA F
  - 22056757_ANEL VEDACAO PLAST. P/ PORTA F
- O registro aparece como ATIVO e identificado N.
- O layout real traz ATIVO antes de uma flag final N; esse era o motivo do descarte pelo parser antigo.
- O teste test_parse_dsploc_accepts_status_before_final_flag protege esse layout.
- O endpoint REST sugerido /technet/equipamentos/{codigo}/equivalentes ainda respondeu 404 em producao; DspLoc permanece a fonte ativa para Atlas.
