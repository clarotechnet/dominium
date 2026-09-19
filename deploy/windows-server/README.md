# DOMINIUM no servidor Windows

## Premissas

- Servidor: `DESKTOP-K7J3E1N`.
- Stack Caddy existente: `C:\Users\Usuario\Documents\sistematoa`.
- Porta reservada para o DOMINIUM principal: `8791`.
- Dominio planejado: `dominium.clarotechnet.com.br`.
- O processo DOMINIUM deve rodar no Windows, nao em container Linux, porque as credenciais Imperium usam Windows DPAPI.

## 1. Checkout

Use uma pasta separada do stack TOA, por exemplo `C:\DominiumMain`.

```powershell
git clone <REPOSITORIO_PRIVADO> C:\DominiumMain
cd C:\DominiumMain
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-web.txt
```

## 2. Segredos

Copie `.env.example` para `.env` no servidor e preencha os valores localmente. `DOMINIUM_PROJECT_ROOT` deve apontar exatamente para a pasta instalada; no layout abaixo, use `C:\DominiumMain`. Nunca commite `.env`, `.secrets` ou `config/*.dat`.

Crie as credenciais Imperium no proprio servidor, usando o mesmo usuario Windows que executara o DOMINIUM:

```powershell
.\.venv\Scripts\python.exe .\scripts\configure_imperium_credentials.py
```

Valide Supabase antes de iniciar:

```powershell
.\.venv\Scripts\python.exe .\scripts\check_supabase_ready.py
```

## 3. Teste local

```powershell
.\deploy\windows-server\start-dominium.ps1
```

O backend escuta em `0.0.0.0:8791` para permitir acesso do Caddy Docker. Nao encaminhe a porta 8791 no roteador. Em producao, mantenha `DOMINIUM_TRUST_PROXY_HEADERS=1` e configure o mesmo valor aleatorio de `DOMINIUM_PROXY_TOKEN` no DOMINIUM e no ambiente do Caddy. O Caddy injeta esse segredo apenas na comunicacao interna com o backend; uma conexao direta na porta 8791 nao deve ser aceita como proxy confiavel. Fora desse desenho, deixe a confianca em proxy desativada.

Se o Chrome TOA ja for mantido por outro componente no mesmo servidor, o DOMINIUM web pode apenas se anexar a essa sessao, sem abrir outro navegador. Configure `DOMINIUM_WEB_ATTACH_TOA=1`, `DOMINIUM_TOA_DEBUG_PORT` com a porta DevTools existente e, quando necessario, `DOMINIUM_CHROMEDRIVER` apontando para um driver compativel. Esse modo inicia somente o monitor/leitor TOA; a automacao local continua desativada.

## 4. Caddy

No stack `C:\Users\Usuario\Documents\sistematoa`, adicione ao `.env.docker`:

```text
DOMINIUM_DOMAIN=dominium.clarotechnet.com.br
DOMINIUM_PROXY_TOKEN=O_MESMO_TOKEN_ALEATORIO_FORTE_DO_DOMINIUM
```

Adicione o conteudo de `caddy-snippet.txt` ao `docker\Caddyfile`. O proxy sera:

`dominium.clarotechnet.com.br -> host.docker.internal:8791`

Depois valide/recrie o gateway somente quando DNS/rede estiverem prontos.

## 5. Atualizacao por Git

Fluxo esperado:

`alterar no DESKTOP-R285TSA -> quality_gate -> commit -> push -> git pull no servidor -> reiniciar DOMINIUM -> smoke test`

No PC de desenvolvimento, antes do push:

```powershell
.\.venv\Scripts\python.exe .\scripts\quality_gate.py
```

No servidor:

```powershell
cd C:\DominiumMain
git pull --ff-only
.\.venv\Scripts\python.exe -m pip install -r requirements-web.txt
```

O mecanismo de reinicio automatico sera configurado na etapa de publicacao, depois de definir a conta Windows que manterá o contexto DPAPI.
