# DOMINIUM web runtime - Hostinger

Runtime Node.js usado para publicar o DOMINIUM na hospedagem Hostinger enquanto o backend oficial do Imperium ainda depende de DataSnap.

## Segurança

- O navegador nunca recebe credenciais do Imperium.
- As credenciais DataSnap entram somente como variáveis server-side: IMPERIUM_DATASNAP_USERNAME e IMPERIUM_DATASNAP_PASSWORD.
- Autenticação do DOMINIUM usa Supabase Auth.
- A sessão fica em cookies Secure, HttpOnly e SameSite=Strict.
- Operações DataSnap deste estágio são somente leitura em /api/orders.
- Rotas de escrita permanecem desabilitadas até migração/homologação.

## Empacotamento

O deploy precisa conter, na mesma raiz do runtime: server.js, package.json, protocol_templates.json e a pasta static/. Os dois últimos vêm da raiz do repositório.
