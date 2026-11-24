# Adesao NTL/PWM: baixa em lote explicita (24/11/2026)

Decisao operacional confirmada pelo usuario com evidencia da baixa manual de
Felipe: equipamentos serializados aplicaveis nunca podem ser dispensados por
falta de saldo; miscelaneas podem ser limitadas ao saldo combinado do tecnico
e RETORNO apos resolver equivalencias oficiais. Omitir saldo zero e preservar
a conciliacao e os motivos no relatorio. Assinatura e INST GPON - INST CABO
recebem somente codigo de baixa. Esta regra substitui a exigencia historica
de bloquear toda a baixa por falta de miscelanea, exclusivamente neste fluxo.

Escopo: perfil natal, buckets NTL-DMV e PWM-DMV, contratos colados pelo operador,
data selecionada, ate 50 distintos. Nenhum ADM, nenhuma varredura geral,
nenhum fallback DataSnap para fechamento. A fila usa a ponte oficial existente,
concilia tarefas e escopos aprovados, bloqueia serial obrigatorio ausente,
evita movimentos duplicados e espera confirmacao por request_id antes da
proxima OS do mesmo contrato. Falhas individuais nao interrompem todo o lote.
A pagina deve permanecer aberta durante o lote; parar impede novos envios,
nao cancela um POST ja iniciado.

O runtime operacional 8765 teve a credencial oficial reconfigurada pelo
operador, sem reinicio. Status official_close_enabled=true confirmado.
Inspecao de codigo desse runtime confirmou alocacao de materiais pelo saldo
do grupo, complemento RETORNO, registro de faltas e validacao de titularidade
dos seriais instalados antes do envio. A UI mostra as dispensas retornadas
pelo backend. Um HTTP aceito nao confirma a baixa. O contrato de referencia
ja foi encerrado manualmente; nao reenviar.

Testes direcionados: 12 testes da fila, 4 da ponte de baixa e regressao
semiautomatica aprovados. Testes usam dados sinteticos, nenhuma baixa ou
movimentacao real executada pelo agente. A captura da lista ao final retornou
stale=true, portanto ausencia do contrato nela nao constitui nova confirmacao.
Homologacao de um novo envio real pelo operador permanece pendente.
