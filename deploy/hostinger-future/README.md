# Hostinger - preparo para migracao futura

Esta pasta NAO e o alvo de producao atual.

Hoje, `dominium.clarotechnet.com.br` deve continuar apontando para o DOMINIUM executado no PC servidor Windows. A separacao aqui existe para que uma migracao futura para a Hostinger nao exija desmontar o runtime atual.

## O que pode ser empacotado agora

O frontend esta em `static/`. Gere um pacote limpo com:

```powershell
.\.venv\Scripts\python.exe .\scripts\build_hostinger_frontend.py
```

Saidas:

- `output\hostinger-frontend\`
- `output\hostinger-frontend.zip`

O build remove backups, temporarios e qualquer arquivo fora da arvore publica de `static/`.

## O que NAO deve ser enviado para a Hostinger

Nunca envie:

- `.env`
- `.secrets`
- `config\*.dat`
- credenciais DPAPI
- tokens de ingestao/proxy
- chave secreta do Supabase
- bancos, logs ou dados operacionais locais

## Limitacao atual

O frontend do DOMINIUM usa endpoints do backend Python. Um upload estatico isolado na Hostinger nao transforma o sistema completo em hosting compartilhado.

Enquanto Imperium/TOA dependerem de Windows DPAPI, o desenho seguro e:

`frontend/publicacao -> backend Windows -> Imperium/TOA`

Antes de uma migracao definitiva, sera necessario definir uma API publica segura ou um canal de comunicacao de saida entre a Hostinger e o agente Windows, mantendo segredos e autorizacao no servidor.
