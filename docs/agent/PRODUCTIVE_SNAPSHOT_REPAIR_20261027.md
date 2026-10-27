# Caso real confirmado e ponte compartilhada preservada

OS2662320818: registroconfirmed409, official_http_status200, accepted14:59:12
e confirmed14:59:18-03:00 em27/10/2026. Counts1instalado/1removido/9miscelaneas.
Attributionunverified no observador legado: nao atribuir origem apenas pelo status
fechado. Usuario confirmou a baixa e mostrou os materiais no Imperium. Nenhum
POST real foi repetido nesta investigacao.

Toast era consulta auxiliar GETinstaller. Worker6afba094 publicado14:56:59
pela alteracao de estoque nao tinha essa rota. A partir da baseStockQuality
d522317 foi criada copia isolada InstallerRouteMerge-20261027; adicionada apenas
a rotaGETinstaller, preservando controle de qualidade e demais alteracoes.
21testesWorker/QC passaram; guarda conferiu versao antes de publicar7590af22.
SmokeQC200/items_arraytrue. Installer deixou404 e atingiu backend400/Atualize
a lista porque esta OS ja saiu do cache de abertas. Main96b5abc posteriormente
integrou ambos os recursos; politica confere emSHA256 eWorker confere ao
normalizarCRLF.30testesJS da base integrada passaram. Pasta do Matheus intacta.

Nova busca4321376 tem falha distinta: TOA_live -> extensao
parseDirectActivityResponse -> toa_provider_nao_encontrado. Resolver nao obteve
nome de tecnico a partir do Provider/caches/PID validado. Nao afirmar que nao
ha tecnico no cadastro nem que login expirou. Consulta cache-only retornou
toa_cache_not_ready. Identificacao tecnica dessa atividade continua pendente;
nenhuma alteracao de extensao, atribuicao de tecnico ou baixa foi feita.

# Publicacao concluida apos repeticao unica

Actions40553080599 tentativa2 concluiu success, incluindo restart e smokes de
producao. Falha Hosting9999/500 da tentativa1 abaixo foi superada.
PR22/mainb8bf3e6, Workerf5170254. Site entregou JS testado com hash conferido.
GETinstaller2231965 pela ponte200, com ID/nome. Nenhuma baixa real executada.
Falta somente validar operacionalmente a baixa com equipamentos/miscelaneas.

# Checkpoint de publicacao

PR22 integrado mainb8bf3e667d784f33eabecac0c7a72d641b5ea0f9.
Workerf5170254-47a0-46aa-8a90-e21d2dc66a00 publicado com recuperacao45b3f101.
GETinstaller2231965 mudou de404 para200 na ponte; ID/nome presentes, sem expor
dados no teste. Nenhum POST de baixa real executado.

Site entregou HTML200/JS200 com referencia20261027-productive-snapshot-1 e hash
04434c1f10fb72aa36e0f405b683de93583d5f79cbf9461298b9815e1dff3451, igual ao testado.
Actions40553080599 primeira tentativa concluiu build, mas falhou no restart da
Hostinger com HTTP500(Hosting9999). Smokes finais foram pulados. Uma repeticao
do job foi solicitada; conferir resultado antes de declarar deploy aprovado.

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
