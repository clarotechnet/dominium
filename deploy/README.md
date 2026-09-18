# Deploy do DOMINIUM

O alvo atual de producao e o PC servidor Windows, com o backend DOMINIUM executando nativamente e o Caddy existente no Docker fazendo o reverse proxy HTTPS.

Arquitetura:

`Internet -> Caddy (Docker, 80/443) -> host.docker.internal:8791 -> DOMINIUM Python no Windows -> Supabase/Imperium`

Use `windows-server/README.md` para o deploy atual.

A configuracao antiga de Ubuntu/Nginx foi preservada apenas para referencia em `legacy-vps/`.
