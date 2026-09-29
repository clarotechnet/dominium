# DOMINIUM — CURRENT STATE

## Status final validado — 2026-09-29

- Runtime operacional carregado no commit `45b67bc`.
- Auto-baixa iniciou com `enabled=true`.
- Primeira rodada com pré-filtro + retry TOA terminou:
  - `seconds=191.46`
  - `ok=true`
  - `closed=3`
  - `bucket_waiting=468`
  - `cache_hits=144`
  - `live_refreshes=50`
  - `lookup_errors=0`
  - `toa_busy_deferred=0`
- Caso real de `toa_consulta_em_andamento` foi resolvido por retry: contrato 1255582 aguardou e depois foi consultado com sucesso.
- `WinError 5` de persistencia continua podendo aparecer como warning de replace atomico, mas o fallback direto impede falha da rodada.
- Quality gate final:
  - 732 testes Python, OK, 21 skips esperados;
  - testes JS `test_disconnect_frontend.js`, `test_operations_monitor.js`, `test_semiauto_frontend.js` OK;
  - Ruff critical OK;
  - build release OK;
  - `QUALITY_GATE_OK`.
- O worker caiu de uma rodada antiga de 1632.13s / 520 live refreshes / 111 lookup errors para uma rodada final de 191.46s / 50 live refreshes / 0 lookup errors.
- O workflow Hostinger ja esta filtrado para nao publicar em commits apenas de backend/worker.

Atualizado em: 2026-09-29 09:54 BRT

## Regra de retomada

Este arquivo e o checkpoint operacional curto do projeto. Ao retomar o DOMINIUM, leia este arquivo primeiro e depois consulte `.dominium/project-map.md` / indices somente se precisar aprofundar.

NAO reinicie o processo 8791 enquanto houver uma rodada de auto-baixa em execucao. A rodada iniciada pelo processo as 09:44:09 estava ativa no momento deste checkpoint e estava realizando baixas reais. Espere aparecer uma nova linha concluida em `logs/auto-improductive-close.jsonl` com `started_at >= 2026-09-29T09:44:09-03:00` antes de reiniciar.

## Git / runtime

- Repositorio: `clarotechnet/dominium`
- Branch: `main`
- HEAD em disco no servidor: `67a79af` — Refresh agent context after TOA bucket prefilter [skip deploy]
- Servidor: `DESKTOP-K7J3E1N`
- Raiz: `C:\DominiumMain`
- Backend operacional: `127.0.0.1:8791`
- Processo em memoria no checkpoint: build `c3af535` (iniciado 09:44:09). O codigo mais novo ja esta no disco/Git e precisa de restart somente depois da rodada atual terminar.
- Auto-baixa: enabled=true, intervalo 300 s.
- Coletor de buckets: ativo a cada 5 minutos.

## Web / Hostinger

- `dominium.clarotechnet.com.br` validado HTTP 200.
- Frontend carrega `/impeccable.css`; arquivo respondeu 200.
- Formulario de cadastro esta presente novamente.
- `/api/auth/session` publico retornou `registration_enabled=true`.
- Edge Function Supabase `dominium-auth-ops` esta na v7 e voltou a executar cadastro; senha 6–128.
- Workflow Hostinger #46 / commit `170581f` terminou SUCCESS.
- Workflow agora so dispara deploy Hostinger para mudancas de runtime web: `static/**`, `deploy/hostinger-web/**`, builder do release ou o proprio workflow. Commits Python do worker nao geram mais deploy web inutil.

## Arquitetura TOA implementada

1. O coletor de buckets roda continuamente e faz merge incremental no registry. Contratos novos que aparecem em importacoes posteriores entram sem zerar os antigos.
2. A janela principal do bucket e a autoridade. Ex.: uma OS 11:00–14:00 nao entra em pesquisa as 10:50 mesmo que o service_window comece 10:45. `service_window` e apenas fallback quando a janela principal estiver ausente.
3. Para contratos de hoje, o status do proprio bucket passou a ser pre-filtro:
   - pendente / iniciado / em rota -> nao abre lookup detalhado;
   - concluido -> entra no lookup detalhado;
   - status ausente -> pesquisa por seguranca.
   Contratos do dia anterior continuam podendo ser consultados diretamente para nao depender de snapshot antigo.
4. O worker 24h e o produtor dos dados TOA detalhados.
5. Resultado concluido e tratado como fotografia final e pode ser reutilizado por ate 24h.
6. Resultado ainda nao concluido usa TTL curto (240 s) para detectar mudanca de status.
7. O botao Baixa Automatica (100%) usa `cache_only=true` e `cache_max_age_seconds=86400`; ele nao deve iniciar uma segunda varredura TOA.
8. Se o cache ainda nao estiver pronto, o frontend mostra `Aguardando coletor TOA`, em vez de pesquisar por conta propria.
9. Coletas startup/manual recentes satisfazem o proximo slot agendado por 120 s, evitando exportar os 13 buckets duas vezes em sequencia.
10. Os estados locais `config/auto_improductive_close_state.json` e `config/toa_bucket_collection_state.json` foram adicionados ao .gitignore.

## Persistencia do worker no Windows

Foi encontrado erro recorrente:
`[WinError 5] Acesso negado ... auto_improductive_close_state.json.tmp -> auto_improductive_close_state.json`.

Correcao:
- tenta replace atomico com retries;
- se o Windows continuar bloqueando rename, faz fallback para overwrite direto sob lock;
- remove o arquivo temporario.

Validacao em runtime: as 09:46:32 e 09:51:55 o Windows bloqueou o replace, o log registrou o fallback e o worker CONTINUOU para os contratos seguintes. O erro deixou de derrubar a rodada naquele ponto.

## Medicao real do bucket em 29/09

Na medicao feita por volta de 09:49:
- 944 contratos do dia no registry;
- 655 contratos com janela principal ja iniciada;
- atividades dentro desse conjunto: 513 pendentes, 244 iniciadas, 41 em rota e 160 concluidas (um contrato pode possuir mais de uma atividade).

Essa medicao motivou o pre-filtro por `activity_status`; a rodada iniciada antes desse codigo ainda esta varrendo o conjunto antigo e por isso e longa.

## Testes

- Gate completo anterior: 721 testes Python, 21 skips esperados, testes JS e Ruff OK.
- Depois dos ultimos fixes foram executadas suites direcionadas de:
  - `tests.test_toa_worker_cache`
  - `tests.test_toa_automation`
  - `tests.test_auto_improductive_close`
- Ruff critico dos arquivos alterados passou.
- Agent context foi regenerado apos as alteracoes e commitado em `67a79af`.

O gate completo deve ser executado novamente no proximo bloco depois que o runtime for reiniciado com o HEAD final.

## Supabase / seguranca

Security Advisor foi consultado.
Avisos atuais:
- RPCs SECURITY DEFINER acessiveis por anon/authenticated. As RPCs web usam bridge token e fazem parte da ponte atual; NAO revogar automaticamente porque pode quebrar autenticacao/bridge.
- Leaked Password Protection do Supabase Auth esta desabilitado.

Hardening desses itens deve ser tratado separadamente, com teste da ponte antes de alterar privilegios.

## Proximo bloco

Este bloco foi concluido. Proximas mudancas devem partir do estado validado acima. Antes de alterar o worker, preserve:
- janela principal do bucket como autoridade;
- pre-filtro por status do bucket;
- cache final de 24h;
- retry de `toa_consulta_em_andamento`;
- fallback de persistencia Windows;
- `cache_only` no botao Baixa Automatica.

## Observacao de ferramentas

Desktop Commander Remote informou 99% da cota mensal durante este bloco. Usar chamadas remotas de forma economica; GitHub e Supabase podem ser operados diretamente pelos respectivos plugins quando nao for necessario tocar no PC.
