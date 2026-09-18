# DOMINIUM - Supabase Auth / checkpoint

Data: 2026-09-17
Escopo: DOMINIUM primario + futuro deploy web. O secundario/TV nao foi alterado.

## Pronto sem intervencao humana

- `supabase/` inicializado com Supabase CLI 2.117.0.
- Migration criada em `supabase/migrations/*_dominium_auth_schema.sql`.
- Schema cria perfis, sessoes, vinculos Imperium e auditoria.
- RLS habilitado e acesso `anon/authenticated` revogado das tabelas server-side.
- `supabase/config.toml` com signup publico desativado e senha minima 10.
- `.venv` isolada criada com `supabase==2.31.0`.
- `supabase_auth_store.py` corrigido para `SyncClientOptions` da SDK atual.
- `.env.example` seguro por padrao: cadastro DOMINIUM desligado.
- `scripts/check_supabase_ready.py` valida Auth + quatro tabelas sem alterar dados.
- `scripts/configure_supabase_hosted.py` configura Auth hospedado via Management API.
- `scripts/deploy_supabase.ps1` faz link, dry-run e push controlado das migrations.

## Arquitetura de login

O navegador autentica somente no backend DOMINIUM. O backend usa Supabase Auth para senha e
mantem role/status/sessoes/auditoria nas tabelas DOMINIUM. A secret key nunca vai ao navegador.

## Amanhã - passos que exigem o dono da conta

1. Fazer login na conta Supabase pelo CLI/browser (`npx supabase@latest login`).
2. Confirmar a organizacao onde o projeto DOMINIUM sera criado.
3. Criar o projeto (regiao recomendada para o Brasil: `sa-east-1`) e definir a senha do banco.
4. Depois disso o restante volta a ser automatizavel pelo ChatGPT/Desktop Commander.

## Sequencia automatizada depois do login

- Obter project ref e API keys via CLI, sem imprimir segredos no chat.
- Definir `SUPABASE_PROJECT_REF` e `SUPABASE_DB_PASSWORD` apenas no ambiente de setup.
- Rodar `scripts/deploy_supabase.ps1` primeiro em dry-run e depois com `-Apply`.
- Aplicar Auth seguro: signup direto desativado e senha minima 10.
- Configurar `SUPABASE_URL` e `SUPABASE_SECRET_KEY` no ambiente privado do DOMINIUM.
- Rodar `scripts/check_supabase_ready.py --require-empty`.
- Criar o primeiro administrador com `scripts/bootstrap_admin.py`.
- Fazer login real pelo DOMINIUM e validar cookie, CSRF, logout e aprovacao de usuario.

Nenhuma senha, service key ou access token deve ser gravado em arquivo versionado.

## Notas de seguranca

- Preferir a nova Secret API Key (`sb_secret_...`) no backend; a variavel usada e `SUPABASE_SECRET_KEY`.
- `SUPABASE_SERVICE_ROLE_KEY` existe apenas como fallback para projeto legado.
- Nao usar publishable/anon key como chave do backend DOMINIUM.
- Nao executar `supabase config push` com o `supabase/config.toml` local completo.
- O deploy usa `deploy/supabase-hosted/supabase/config.toml`, que declara somente as opcoes Auth desejadas.
- Docker local foi propositalmente evitado: daemon desligado e cerca de 12 GB livres no C:.
