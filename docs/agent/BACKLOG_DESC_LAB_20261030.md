# Análise Backlog dentro de DESCONEXÃO — 30/10/2026

## Interface
A navegação no site **já possui** o grupo **DESCONEXÃO** (WhatsApp · Atlas, Visão Claro). A nova opção **Análise Backlog** é a terceira filha do grupo. O menu, o destaque do grupo e o hash `#desconexao-backlog` foram incorporados sem criar um novo agrupamento de desconexão ou duplicar recursos. Telas internas: Entrada, Fora de Rota e Rotas Enviadas; códigos em filtro expansível, técnicos reutilizam o cadastro existente.

## Fontes
- Rotas Claro: importação manual CSV/XLSX em memória e histórico SQLite local do servidor, sem usar o Cloudflare D1 antigo.
- História Imperium: DataSnap, por um dia/perfil, lendo OS concluída e o **CódigoBaixa** oficial do detalhe. 4 perfis abrangem Natal/Parnamirim, Fortaleza, Mossoró e Recife. `backlog_imperium_year.py` calcula último ano completo até ontem e resume cursor por perfil.
- Banco: `LOG_ROOT/backlog_year/history.sqlite3` no servidor operacional. Sem escrita no D1 antigo ou Supabase operacional.
- A função Fora de Rota no laboratório é uma **pré-lista** baseada no último histórico confirmado em 106 e exclusão da rota importada. Ainda **não substitui** a verificação TOA atual nem a lógica completa de bairros/agenda do site antigo.

## Segurança
- Nenhuma ferramenta faz baixa, modifica O.S., transfere equipamentos ou emite mensagens WhatsApp automaticamente.
- API do DOMINIUM exige autenticação, perfil operacional e CSRF para escritas.
- Leitura DataSnap disputa o `OPERATION_GATE` com as rotinas produtivas; se ocupado, espera e falha sem alterar checkpoint.
- Carga anual segue **desabilitada por padrão**, via `DOMINIUM_BACKLOG_YEAR_ENABLE != 1`, até validar um piloto real. A opção `Testar ontem` consulta no máximo 3 detalhes e não importa registros.
- O leitor possui cursores por dia e idempotência; o frontend reinicia lotes gradualmente enquanto aberto. Ainda não há agendador independente do navegador.
- O proxy Hostinger serve arquivos estáticos novos; o bridge Hostinger → API Python autenticada e o acesso com CSRF do usuário final precisam de teste integrado real antes da produção.

## Testes executados
- 13/13 testes do módulo anual e importação XLSX padrão aprovados.
- Regressão de planilha com várias abas, cabeçalhos alternativos, nome de arquivo com '(1)' e cidade inferida de 'NTL': aprovada.
- 14/14 testes Node relacionados à DESCONEXÃO, hostinger e fluxo frontend aprovados.
- Python py_compile e node --check aprovados para módulos alterados.
- Empacotamento Hostinger gerado e ZIP íntegro; frontend novo presente no release.
- Quality gate completo: 1.010 testes; 3 erros de limpeza de bases SQLite temporárias no Windows em testes antigos Atlas QUERY. Reproduzidos em baseline original (18 testes, os mesmos 3 erros), portanto não são regressão deste módulo. Ainda assim o gate global não está verde.
- Teste DataSnap histórico no servidor operacional: **não validado**; tentativa controlada foi bloqueada pela segurança da ferramenta, não inferir sucesso.
- Teste ponta a ponta da sessão Hostinger/operacional e do gerador Fora de Rota no TOA: **não validado**.

## Deploy e rollback
Mantenha este PR em **draft**. Não publicar UI isoladamente, pois o backend operacional precisa ter as rotas novas antes de habilitar. Precisa de uma versão do servidor verificada, backup do código, piloto DataSnap read-only, validação de autenticação, prova das cinco cidades, navegação real e rollback. Não alterar `main` ou serviços DESC existentes nesta etapa.

## Estado
Branch de desenvolvimento baseada no `origin/main` atual `5dc1403` — sem alterações no checkout do operador, sem upload de dados legados D1 e sem baixa real.
## Validacao TODOS/TODOS — 30/10/2026
- Teste DataSnap somente leitura: Natal 29/10/2026. Filtro TODOS/TODOS retornou 764 OS. Quatro filtros individuais: field 2, completed 538, canceled 41, rescheduled 134, total de 715 OS. 49 OS adicionais nao pertencem a esses quatro grupos.
- A nova sincronizacao usa a consulta TODOS/TODOS como fonte principal, preserva os 49 com status DESCONHECIDO, anota os status individuais quando identificados e verifica o CodigoBaixa real no detalhe.
- Comparativo original: qualquer historico com um codigo selecionado (101, 306, 404, 430 por padrao) marca SEGURAR. O backend novo reproduz essa regra. Codigo 106 e usado na analise de Fora de Rota. Sem historico confirmado nao implica baixa.
- Hostinger e Worker: allowlist de GET status/compare/fora-rota/sent e POST start/pause/routes/sent, com limites e cargo admin/controller. Nenhuma nova rota autoriza baixar OS.
- Backend: helper backlog_bridge_auth exige DOMINIUM_BACKLOG_BRIDGE_TOKEN forte, cliente loopback, ator identificado e cargo operacional. Sem token, retorna negado.
- 20 testes Python + 41 Node passaram, com validacao de sintaxe e release ZIP. D1 legado nao foi migrado; SQLite isolado e a fonte do laboratorio.
- Bloqueador de deploy: backend operacional no servidor tem diferencas em relacao ao main; exige reconciliacao, backup e configuracao privada da credencial. Nao publicar antes de teste HTTP fim a fim. A carga anual segue desabilitada por padrao.## API independente no servidor — laboratorio
- Novo backend autonomo backlog_sidecar.py, escutando somente 127.0.0.1:9342, sem substituir app.py antigo. Codigo copiado para C:\DominiumRuntime\BacklogLab-20261030\app, base SQLite sob data.
- Usa token forte existente do Relay DESC por arquivo local de acesso restrito, sem copiar credenciais ao GitHub e sem expor o token no navegador.
- Worker VPC agora encaminha apenas endpoints do Backlog a 127.0.0.1:9342; os caminhos existentes 8765 e 8793 continuam os mesmos.
- Teste HTTP direto ao servidor validou 401 anonimo/viewer, 200 GET status, 423 carga anual bloqueada, 200 importacao CSV ficticia e comparacao, 202 inicio piloto DataSnap.
- Piloto DataSnap real terminou completed com 3 codigos confirmados, 0 itens no historico persistente e nenhum checkpoint alterado.
- 25 testes Python e 27 testes Node passaram nessa etapa; daemon da porta 9342 iniciou em laboratorio.
- Ainda NAO foi feito deploy do Worker/Hostinger, nem teste autenticado pela internet. A fonte Supabase continua opcional; o D1 antigo nao participa desta integracao.