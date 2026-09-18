# CHECKPOINT WEB READY - 17/09/2026

Status: preparacao web concluida localmente no DESKTOP-R285TSA.

Concluido:
- backend de autenticacao selecionavel: sqlite, postgres ou supabase;
- Supabase Auth + tabelas de perfil, sessao, identidade Imperium e auditoria;
- bootstrap inicial de admin somente por script no servidor em modo web;
- cadastro publico controlado por variavel de ambiente;
- cookies/CSRF/origem publica preparados para HTTPS;
- modo web nao inicia automacoes/navegadores TOA locais;
- Nginx preparado para proxy em 127.0.0.1:8765;
- systemd, .env.example e requirements-web.txt criados;
- script scripts/bootstrap_admin.py criado;
- schema supabase_schema.sql concluido;
- .env e artefatos sensiveis ignorados pelo Git.

Validacao final:
- Python py_compile: OK
- node --check static/app.js: OK
- 55 testes relacionados: OK
- smoke HTTP em DOMINIUM_WEB_MODE=1: 200 OK

Reuniao TECHNET/Jader revisada:
- login oficial Imperium com jwtusername/jwtpassword + Bearer ja esta coberto no cliente HTTP;
- Id-Usuario, Id-Estoque, Grupo-Usuario e Usuario podem futuramente enriquecer o perfil DOMINIUM;
- estoque oficial e demais endpoints ficam como evolucao separada, com contrato/testes proprios.

Nao realizado:
- deploy real no Hostinger;
- criacao/configuracao do projeto Supabase real;
- DNS/certificado do dominio real;
- migracao do bot/TOA para o VPS (ele deve permanecer separado).
