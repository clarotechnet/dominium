# DOMINIUM — rollout Imperium DataSnap / Supabase / Atlas (06/11/2026)

## Composição do fluxo
- Fase 1: pesquisar equipamentos usados no DataSnap por cidade/período.
  O serviço salva o dataset de ordem de serviço e os seriais únicos
  no Supabase operacional `haqzzxpocwzntyudrbch`. Não exige XLSX.
- Fase 2: tratar cada serial individualmente por API DataSnap somente leitura,
  com progresso, pausa, repetição e persistência de cada resposta.
- Fase 3: consultar evidências do Atlas por equipamento, conferir
  serial solicitado versus serial retornado e registrar pendências.
- Exportação parcial auditável: Seriais Tratados, Pendências,
  Conferência Atlas, Pendências Atlas.

## Evidência de referência
A coleta real de Natal de 05/11/2026 contém 1.096 registros por OS,
209 seriais únicos e 887 registros sem serial. Ela corresponde ao
arquivo de referência enviado pelo operador.

As tabelas `dominium_imperium_consultas`,
`dominium_imperium_consulta_lotes` e
`dominium_imperium_tratamento_itens` foram instaladas no projeto
Supabase operacional pelo operador e confirmadas via API privada.
O fluxo persistiu os 209 seriais e comprovou uma tratativa individual.

## Infra / publicação
- Relay privativo: `DESKTOP-K7J3E1N`, porta 8793,
  atualizado com arquivos isolados do projeto, sem substituir
  o Dominium principal na porta 8791. Backup:
  `C:\DominiumRuntime\DescRelay-20261010\backups\imperium-two-stage-20261106`.
- Canary de relay na porta 8794 confirmou histórico, Atlas e
  bloqueio de acesso não autenticado.
- Cloudflare Worker `dominium-import-bridge` atualizado via Wrangler
  v4.124.0, versão implantada
  `36eada86-128e-46c4-a58f-0395c73ab0da`.
  Histórico de versões pré-atualização guardado somente no
  computador do operador em
  `C:\DominiumRuntime\PrivateReference\CloudflareBeforeDeploy20261106.json`.
  Os 19 testes específicos do Worker passaram, incluindo rotas
  antigas TOA/Import e novas DataSnap/Atlas/seriais.
- Interface Hostinger: workflow
  `.github/workflows/hostinger-account-diagnostic.yml`
  valida e publica automaticamente alterações de `static/**`
  e `deploy/hostinger-web/**` ao receber push em `main`,
  desde que o último commit não contenha `[skip deploy]`.

## Verificações antes de acionar a Hostinger
- 148 testes Node de deploy aprovados.
- 56 testes Python aprovados.
- Sintaxe JavaScript e `git diff --check` aprovados.
- Sem SQL adicional nem modificação de saldo/OS no Imperium.
- O Worker não expõe a chave Supabase ao navegador.

## Limitações conhecidas
A exportação intermediária de quatro abas NÃO equivale
ao relatório de seis abas do vídeo. A origem de datas e
a conciliação completa com Atlas, Assinantes, Nomes. e
conferência de estoque físico ainda não foram homologadas.
Consulta individual por serial permanece homologada
inicialmente em Natal (seriais de 12 caracteres).
Seriais ICCID de 20 caracteres são identificados como
formato pendente, não como inexistentes.

## Reversão
- Cloudflare: `wrangler rollback` com versão anterior registrada
  no arquivo privado acima.
- Relay: restaurar os arquivos do backup, reiniciar a porta 8793,
  verificar autenticação e o endpoint legado.
- Hostinger: usar o deploy anterior registrado no histórico
  GitHub Actions/Hostinger ou publicar release anterior da `main`.
