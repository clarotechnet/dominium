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

## Revisão com SAFRA DADOS EPO.xlsx real — 23/11/2026

Origem: planilha recebida pelo operador no ChatGPT, analisada fora do servidor (NÃO foi copiada para o repositório ou servidor). Arquivo com 22.866.970 bytes; modificado no Excel em 19/11/2026. Abas DIN e Safra; Safra possui 25 colunas e 26.276 linhas de dados, representando equipamentos. Há 22.237 chaves BASE_CD_NET distintas em 39 cidades.

Campos importantes da Safra: DATA_PEND, NM_CIDADE, CD_NET, BASE_CD_NET, NOME, ENDEREÇO, BAIRRO, DX22, TELEFONE NETSMS, TELEFONE TEL, TEL URA, NR_SERIAL e NR_MAC. A data de pendência é valor serial do Excel; não é data de baixa.

Contagens por BASE_CD_NET na área atual do seletor: Natal 1.998; Parnamirim 244; Fortaleza 3.239; Mossoró 224; Recife 1.942; Jaboatão dos Guararapes 278; Olinda 114. Total nessas sete cidades: 8.039. É contagem da lista Claro, ANTES de cruzar com 106 limpo e enviados. A cidade Paulista tem 283 contratos, e o operador confirmou em 23/11/2026 que a operação Recife NÃO atende Paulista. Descartar os contratos de Paulista nas importações semanais de Fora de Rota, sem incluí-los em Recife/Pernambuco. Não apagar os dados originais recebidos na planilha.

Há 42 números CD_NET encontrados em múltiplas BASE_CD_NET de cidades diferentes, dos quais 13 têm pelo menos uma ocorrência nas cidades atendidas. Nenhum dos 42 se repete dentro de um mesmo perfil operacional atual. NÃO usar apenas CD_NET como chave global da Safra; manter BASE_CD_NET e escopo/cidade.

Entre as 8.039 chaves de cidades atendidas, 2.254 não apresentam nome, endereço, bairro e telefone mesmo após reunir as linhas de equipamentos. O código original gera traços '-' para campos ausentes; revisão humana é indispensável antes de contato. Não supor que código 106 corrige esse problema. Adição futura recomendada: indicador de cadastro incompleto e bloqueio de envio automático; não ocultar contratos silenciosamente.

A primeira implementação havia limitado o upload a 12 MiB e rejeitaria este arquivo. Nesta revisão o limite passou a 32 MiB; para evitar exceder sessionStorage, só são persistidas as sete cidades que o seletor atual já atende. Assim, a importação de Safra das 39 cidades NÃO é migrada para a base compartilhada do Dominium. As bases ainda são locais à sessão. A implementação precisa de storage central versionado para atualizações semanais e migração do histórico Firebase/Cloudflare antes de deploy.

O site original importa a SAFRA pela aba Fora Rota, agrega equipamentos por BASE_CD_NET, cruza contratos com a base 106 limpa de Imperium (último evento 106, sem 430), filtra por cidade/bairro e exclui enviados. Depois gera mensagem WhatsApp contendo contrato, nome, endereço, agenda, telefones, técnico e equipamentos; copiar texto é distinto de marcar enviado. Enviados são tratados como registro operacional e podem receber atualização do bot; não equivalem a baixa confirmada.

Nesta revisão também foram corrigidos aliases de TELEFONE NETSMS / TELEFONE TEL / TEL URA e o separador '_' entre telefones. Testes sintéticos de telefone e duplicidade entre cidades executados; não se executou o XLSX real no site nem se modificou a base Firebase. Sem envio de mensagens, sem baixa de OS e sem mudança de produção.
