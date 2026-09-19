# Deploy do DOMINIUM

O alvo atual de producao e o PC servidor Windows. O backend e o frontend do DOMINIUM continuam sendo servidos pelo processo Python nesse computador, e a borda publica deve apenas encaminhar HTTPS para ele.

Arquitetura atual:

`Internet -> entrada HTTPS/tunel/reverse proxy -> DOMINIUM Python no Windows:8791 -> Supabase/Imperium/TOA`

Use `windows-server/README.md` para o deploy de hoje.

A pasta `hostinger-future/` e o script `scripts/build_hostinger_frontend.py` deixam o frontend separado e empacotavel para uma migracao futura. Esse pacote nao substitui o backend Windows: as rotinas Imperium/TOA usam DPAPI e dependem do mesmo usuario/maquina enquanto essa integracao nao for redesenhada.

A configuracao antiga de Ubuntu/Nginx foi preservada apenas para referencia em `legacy-vps/`.
