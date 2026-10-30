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
