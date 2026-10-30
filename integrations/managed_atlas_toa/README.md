# Login Claro — extensão gerenciada Atlas/TOA

**Status (30/10/2026):** extensão `TOA TechNet Bridge` versão
`2.6.14` modificada e recarregada no Chrome for Testing do servidor
`DESKTOP-K7J3E1N`. O script `claro-login-submit.js` foi instalado no
perfil gerenciado `C:\DominiumRuntime\ManagedAtlasTOA-20261022\extension`
e incluído em `manifest.json` com permissão limitada a
`https://cap.claro.com.br/loginapp2fa/*`.

## Regra e limites

Quando o navegador estiver **exatamente** na primeira página
`cap.claro.com.br/loginapp2fa/`, o script observa o formulário
`input[name="username"]`, `input[name="password"]` e botão `ENVIAR`.
Se **ambos** tiverem valores já preenchidos no navegador (ex.: Chrome
Password Manager), o script:

1. Limpa cada campo usando o setter nativo;
2. Reinsere os mesmos valores já existentes, disparando eventos `input`
   e `change`;
3. Registra uma tentativa em `sessionStorage`, sem credenciais;
4. Clica em `ENVIAR` uma única vez.

**Não é um provedor de credenciais.** O login e a senha fornecidos no chat
não foram inseridos no código, no repositório, nos arquivos de log, nem
num cofre remoto. Nenhum segredo deve ser versionado no DOMINIUM.
Os campos estavam vazios depois da recarga do navegador, portanto o
login automático completo **não foi comprovado**. Para preencher
automaticamente nas próximas visitas, um operador autorizado precisa
salvar suas credenciais no gerenciador de senhas desse perfil Chrome,
por interface local/autorizada. Se o navegador não preencher, o script
aguarda preenchimento manual, sem clicar em campos vazios.

Não manipula CAPTCHA, 2FA nem outros domínios. Se encontrar um desafio,
não faz clique. `sessionStorage` bloqueia nova tentativa por 60 segundos
no mesmo origin; a rotina é encerrada após o primeiro clique, evitando
repetições em loop. O conjunto existente de scripts TOA/Atlas segue
intacto; apenas a permissão e o `content_script` foram adicionados.

## Testes

No servidor:
```cmd
node --check C:\DominiumRuntime\ManagedAtlasTOA-20261022\extension\claro-login-submit.js
node C:\DominiumRuntime\ManagedAtlasTOA-20261022\extension\test-claro-login.cjs
```
Cinco cenários aprovados com valores fictícios: preenchido/clica,
vazio/não clica, desafio/não clica, outro domínio/não clica,
tentativa recente/não repete. O `manifest.json` passou na leitura JSON,
e a API local CDP confirmou que o service worker carregou o script.
A página de login permaneceu aberta e com os campos vazios: nenhuma
autenticação real foi confirmada.

## Instalação e rollback

Cópias versionadas: `integrations/managed_atlas_toa/claro-login-submit.js`
e `integrations/managed_atlas_toa/test-claro-login.cjs`.
A edição do manifesto em produção foi feita de modo cirúrgico, com
backup `manifest.json.before-claro-login-20261030`. Não substituir
o restante da extensão por arquivos do repo, pois o runtime do servidor
pode conter alterações locais ainda não integradas.

Para reverter: restaurar o backup do manifesto, remover
`claro-login-submit.js`, e recarregar a extensão. Não reiniciar
serviços de baixa de O.S. nem alterar o lote 106 para essa operação.
