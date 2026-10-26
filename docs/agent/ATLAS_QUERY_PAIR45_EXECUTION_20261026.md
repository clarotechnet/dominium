# QUERY Atlas — principal, reserva45s e antecipação FALHOU

## Estado verificado — 26/10/2026, 13:58 (America/Sao_Paulo)

Implementado, testado e publicado na main: 2475433f08519b651dd4fa09313813989db5b7f5.
A árvore publicada 0d5c2b29643e39bc8622e0a17fb0c6be76d11eb6 é exatamente igual à
árvore do commit local testado f0b42e8. Publicação autorizada diretamente pelo
usuário após bloqueios de aprovação anteriores; conexão GitHub usada porque
o Git CLI local não tinha autenticação. Nenhum bloqueio foi contornado.

## Comportamento

- ID principal confirmado inicia prazo persistente de45s.
- Reserva única após45s, mesmo se principal pronto; antecipada somente quando
  Atlas confirma failed/remote_queue_failed com ID principal conhecido.
- Leituras desconhecidas, timeout e autenticação não antecipam a reserva.
- Transação/índice único protegem concorrência; submissão incerta não é reenviada.
- Página de processos real precisa confirmar conclusão antes dos anexos;
  somente arquivo válido interpretado libera relatório e exportações.
- UI acompanha doisIDs, preserva retomada e impede novo par enquanto pendente.

## Testes e publicação

Gate completo aprovado:945 testes Python,21 ignorados; suítesJavaScript,
Ruff, auditoria, contexto ebuild aprovados. Revisão independente do ajuste
FALHOU sem achados importantes. Revisão anterior teve duas correções cobertas
por regressões: reconciliação semID e refresh comreserva404esgotada.
Actions40363394318 (Deploy Hostinger DOMINIUM):completed/success.
UI asset20261026-3 observado no navegador; downloadHTTP200 doJavaScript igual
byteporbyte ao código testado, SHA256e8bdb080bf9190b2a316ea104d3a5a0bc231759e47029dab9bd7e2ea19804972.

## Instalação do relay

Executado deploy com mutex do watchdog, cópia prévia dos três módulos eSQLite
backupquery_jobs.before-pair45-20261026-135344.sqlite3, integridadeok.
Reiniciado somente relay, Chrome preservado. Log finaldeployed:
25trabalhos/183194linhas preservados; GETautenticado200, anônimo401.
Hashes instalados iguais aos publicados:
- HTTP:26a03f23d7083585252c6a19570c7e4046fdd17021eb6f62ec6321e408c4123f
- pipeline:99fd8c794634cc5d25bebe20bf55cada819c1fff15365bd2ec2922e769673bd3
- report:3cf7a75c9d2f14406da6d28263ac91a2c44753e0667aaddfa4cb74ad591a4e92

## Teste real pela interface

Clique explícitoNatal/Empreiteira, solicitação prefixoff757346:
principal276935365 e reserva276935412. Horários do servidor exibidos:
principal solicitado13:56:00, IDconfirmado/atualizado13:56:11,
reserva solicitada13:56:57:46s após confirmação, tolerância do scheduler1s.
Os relógios navegador/servidor diferem; não subtrair timestamps de origens distintas.
Recarga recuperou os mesmosIDs e não criou nova solicitação.
Às13:58, interface informa attachment404/aguardando disponibilidade, semtabela,
CSV/XLSXdesabilitados. Não afirmar que ambos individualmente foram consultados
nesta etapa: aUI apresenta o estado ativo da família.

## Limitação e continuidade

Após instalação, Desktop Commander atingiu cota mensal e bloqueou todas as
novas chamadas; não foi reconectado nem contornado. Inspeção direta do novo
par noSQLite e validação original/parser/exports ainda pendentes. A publicação
foi verificada porGitHub/Actions, hashes eUI; não equivale à aprovação completa
da geração automáticaNatal. Não gerar mais IDs neste acompanhamento.

Natalmanual276922051 permanece o relatório20145linhas aprovado anteriormente;
não usar esse sucesso para concluir o novo par. Preservar relatóriosFortaleza
276907771/29529,Recife276907778/55749 eMossoró276907784/892.
Não foram executadas açõesTOA/baixas/estoque/contrato/OS nesta intervenção.
