# Baixa produtiva — snapshot e consulta de tecnico

Contrato3139094, OS2662320818/IdOS2231965: runtime14:28:06 confirmou
OperationBlocked(stale_snapshot,operation_blocked) em _validated_close_operation
1096, por approved_state_hash diferente do snapshot vigente. Falhou antes de
preparar materiais ou chamar a API oficial. OS2662320829 foi confirmada409.

Consulta TOA atualiza snapshots no backend. Frontend mantinha state.orders
anterior e prepareToaLiveClose misturava hash antigo com identidade/import_scope
da busca nova. Agora linhas autorizadas e exatas sao atualizadas integralmente
ao receber a busca; editor usa uma linha coerente, sem fallback por campo.
Se state.orders mudou durante a busca, resposta tardia e rejeitada, sem sobrescrever
lista nova. Validacoes do servidor permanecem; materiais/equipamentos preservados.
Fontes manuais/historicas aprovadas mantidas. Nenhum POST real repetido.

Print adicional revelou GET /api/orders/2231965/installer404: faltava somente
leitura installer na politica privada. GET material-inventory ja respondia200.
Rota GET adicionada; POST installer segue bloqueado. Nenhuma mutacao nova.

34 testes JS focados,949 Python com22ignorados,JS/Ruff/build e3testes de release
passaram. Revisao independente encontrou corrida de resposta atrasada; corrigida
com RED/GREEN e gate completo novamente. Teste comportamental usa prepare e
submit reais e preserva9materiais, quantidade78 e equipamento, com uma chamada.

Worker anterior45b3f101 e recuperacao preservados em
C:\DominiumRuntime\ProductiveSnapshotFix-20261027. Publicacao em andamento.
Baixa real com equipamentos/materiais continua pendente de teste operacional.
