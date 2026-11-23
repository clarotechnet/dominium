# DOMINIUM — incorporação do gerador Fora de Rota (23/11/2026)

## Escopo entregue nesta branch (sem deploy)

- Branch de homologação: feat/fora-rota-isolated-20261123, derivada de
  fix/backlog-technician-names-20261119, cujo backlog-analysis.js coincidia
  exatamente com o JS que o site Dominium publicava em 23/11.
- Fonte de regras: C:\Users\Usuario\Documents\analise-backlog-rescue\public\fora-rota.js.
  A rotina não foi reescrita do zero: importação Safra/BASE_CD_NET, separação
  por base/cidade, regra de 106 limpo, formatação de WhatsApp e filtros vêm da fonte.
- HTML/CSS: nova seção de gerador detalhado dentro da aba Fora de Rota,
  mantendo intacto o botão antigo "Gerar lista".
- JS: static/backlog-fora-rota.js. Importa Claro e Imperium em .csv/.xls/.xlsx,
  associa base 106 à cidade, filtra bairro/quantidade, gera texto para WhatsApp,
  copia texto e oferece marcação manual no endpoint autenticado já existente
  /api/backlog/year/sent. Nenhum disparo de mensagem ou baixa de OS.
- O registro de envio consulta GET /api/backlog/year/sent antes de enviar
  POSTs, deduplica por perfil+código de contrato e não usa Firebase diretamente.
  O GET/POST só marca registro no Dominium, sem execução técnica.
- Planilhas e metadados contendo dados de clientes permanecem na sessionStorage
  (somente sessão de navegador), nunca são enviados a Firebase/Cloudflare.
  A carga de XLSX é sob demanda, limitada a 12 MB, usando SheetJS CE 0.20.3.
  A cópia de licença Apache 2.0 acompanha a distribuição no diretório static/vendor.

## Limites importantes ANTES DE DEPLOY

1. O legado conserva bancos compartilhados em Firebase/Firestore:
   imperiumDashboard/foraRotaState, foraRotaClean106Chunks, foraRotaClaroChunks,
   foraRotaSentContracts. O Dominium não recebeu migração desses dados.
   A API de enviados do Dominium pode não conter os enviados no painel antigo.
   Portanto ainda NÃO se pode alegar deduplicação completa entre os dois sites.
2. Histórico 106 e Claro importados desta forma não são compartilhados entre
   computadores/usuários: apenas a sessão atual. Para equivalência plena,
   criar armazenamento central, autorização por cidade, trilha de auditoria,
   importação versionada e reversível, teste de concorrência e migração.
3. O legado recebe retorno de baixas pelo bot e mostra código/data/mensagem.
   A API /api/backlog/year/sent atualmente registra envio; não confirmar
   código de baixa nem inferir retorno pelo simples registro.
4. Integrar dados legados requer exportação autorizada do Firestore e confirmação
   do mapeamento de cidade/base; não armazenar credenciais em repositório/chat.
5. Não fazer commit/push/deploy sem revisão de segurança, pacote, testes,
   migração histórica e aprovação operacional da publicação.

## Testes reproduzíveis

node --check static/backlog-fora-rota.js
node tests/test_backlog_fora_rota.cjs
node tests/test_backlog_action_buttons.cjs
node tests/test_backlog_status_reload_20261107.cjs
python scripts/build_web_release.py

O teste novo cobre regra de 106 mais recente, veto por qualquer 430,
empate por ordem da planilha, contrato com mesmo número em bases distintas,
importação do histórico, ligação DOM, POST autenticado simulado, deduplicação
contra GET e isolamento de cidades. Não usa dados de clientes reais.

## Próxima etapa

Planejar store central seguro, importar os snapshots legados sob autorização,
consultar status de envio pela API e só depois publicar em produção.
A origem do Cloudflare Worker é https://analise-backlog.dmv-analise-backlog.workers.dev/#fora-rota.
A fonte local resgatada é datada de 24/09/2026 e as diferenças de versões
devem ser revisadas antes de uma migração de dados.

## Quality gate e isolamento
Suite global (23/11): 1116 testes, 22 skips, 4 erros ja conhecidos de SQLite/asset e 1 teste de tecnico intermitente. O teste de tecnico isolado passou 4/4. A integracao fica sem deploy ate revisao final.
Isolado em C:\DominiumRuntime\ForaRotaIntegration-20261123 para nao concorrer com alteracoes simultaneas no checkout BacklogNames-20261119.
