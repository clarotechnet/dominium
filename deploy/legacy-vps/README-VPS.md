# DOMINIUM - deploy web no Hostinger VPS

Arquitetura prevista:

Browser -> HTTPS/Nginx -> DOMINIUM em 127.0.0.1:8765 -> Supabase Auth/Postgres + Imperium.
O coletor TOA permanece separado no servidor/bot e envia dados usando DOMINIUM_INGEST_TOKEN.

## 1. VPS

Use Ubuntu LTS. Crie um usuario de servico `dominium` e instale Python, venv, Nginx e Certbot.
O codigo deve ficar em `/opt/dominium` e pertencer ao usuario `dominium`.

Exemplo de preparacao:

```bash
sudo useradd --system --home /opt/dominium --shell /usr/sbin/nologin dominium
sudo mkdir -p /opt/dominium
sudo chown -R dominium:dominium /opt/dominium
python3 -m venv /opt/dominium/.venv
/opt/dominium/.venv/bin/pip install -r /opt/dominium/requirements-web.txt
```

## 2. Supabase

Crie um projeto Supabase e execute `supabase_schema.sql` no SQL Editor.
Use a secret/service-role key somente no servidor. Ela nunca deve ir para JavaScript, HTML ou Git.
Copie `.env.example` para `/opt/dominium/.env` e substitua todos os placeholders.

## 3. Administrador inicial

No modo web o primeiro visitante NAO pode se promover a administrador.
Depois de configurar o Supabase e o `.env`, rode no VPS:

```bash
cd /opt/dominium
set -a; . ./.env; set +a
./.venv/bin/python scripts/bootstrap_admin.py --username SEU_USUARIO --display-name "Seu Nome"
```

A senha sera solicitada sem aparecer no terminal. Depois disso, novos usuarios podem se cadastrar e ficam pendentes ate um admin aprovar.

## 4. Nginx e systemd

Troque `dominium.seudominio.com.br` pelo dominio real em `.env.example` e `deploy/nginx-dominium.conf`.
Instale o service e o site Nginx, valide as configuracoes e emita o certificado TLS com Certbot.

```bash
sudo cp deploy/dominium.service /etc/systemd/system/dominium.service
sudo cp deploy/nginx-dominium.conf /etc/nginx/sites-available/dominium
sudo ln -s /etc/nginx/sites-available/dominium /etc/nginx/sites-enabled/dominium
sudo systemctl daemon-reload
sudo systemctl enable --now dominium
sudo nginx -t && sudo systemctl reload nginx
```

## 5. Regras de producao

- Nao exponha a porta 8765 no firewall; somente Nginx acessa o backend.
- Libere 80/443 e restrinja SSH conforme a administracao do VPS.
- Mantenha `DOMINIUM_HTTPS=1` e o `DOMINIUM_PUBLIC_ORIGIN` exatamente igual ao dominio HTTPS.
- Mantenha `DOMINIUM_ALLOW_WEB_BOOTSTRAP=0`.
- `SUPABASE_SECRET_KEY`, credenciais Imperium e `DOMINIUM_INGEST_TOKEN` sao segredos de servidor.
- Nao copie `.env`, `config/*.dat` ou bancos locais para repositorios publicos.
- O bot/TOA deve autenticar ingestao com `Authorization: Bearer <DOMINIUM_INGEST_TOKEN>`.

## 6. Validacao

Antes de reiniciar producao:

```bash
./.venv/bin/python -m py_compile app.py api_security.py auth_store.py supabase_auth_store.py
./.venv/bin/python -m unittest tests.test_api_security tests.test_auth_store
sudo nginx -t
sudo systemctl status dominium --no-pager
```

O backend PostgreSQL proprio (`auth_store_postgres.py`) foi mantido como alternativa de compatibilidade, mas a configuracao recomendada para o deploy novo e `DOMINIUM_AUTH_BACKEND=supabase`.
