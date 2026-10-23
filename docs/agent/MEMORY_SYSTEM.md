# DOMINIUM Memory — memória portátil para ChatGPT, Codex, Claude e outros

## O que é

Um sistema gratuito e aberto de memória externa: Markdown **curado** no Git,
mapas auto-gerados do código, histórico Git e índice local SQLite FTS5.
O cache SQLite fica em `output/agent-memory.sqlite3` e pode ser apagado ou
reconstruído a qualquer momento. Não depende de APIs pagas, nuvem externa
ou de memória proprietária de uma IA.

## Como começar do zero, em qualquer conta/modelo

1. Abrir repositório DOMINIUM autorizado.
2. Ler `AGENTS.md` e `docs/agent/memory/CURRENT_STATE.md`.
3. Rodar `python scripts/agent_memory.py brief`.
4. Buscar a tarefa com `python scripts/agent_memory.py search "<assunto>"`.
5. Encontrar símbolos com `python scripts/query_agent_context.py "<termos>"`.
6. Ler somente código, testes e decisões retornados; verificar estado real.

Instruções dedicadas apontam sempre à mesma memória:
`CLAUDE.md`, `GEMINI.md`, `.github/copilot-instructions.md`,
`.cursor/rules/dominium-memory.mdc`. O índice do código vive em
`.dominium/`.

## Atualizações automáticas e humanas

- **Automático:** hook de pré-commit registra paths staged em
  `docs/agent/memory/AUTO_CHANGES.md`; atualiza índices.
  Git armazena autoria, mensagem, diff e quando a mudança ocorreu.
- **Semântico:** ao terminar tarefa, agente responsável atualiza
  `CURRENT_STATE.md` e usa o comando `record` com fatos verificados.
  Hook algum é capaz de adivinhar corretamente motivação, resultado
  de teste ou status de deploy.
- **Primeiro clone:** execute
  `python scripts/install_agent_context_hooks.py`, pois hooks Git não
  viajam automaticamente com o repositório.
- **Validação:** `python scripts/agent_memory.py doctor`,
  `python scripts/generate_agent_context.py --check`,
  `python scripts/quality_gate.py`.
- **Histórico:** `python scripts/agent_memory.py history --limit 15`.

## Regras de segurança

Jamais registrar senhas, tokens, cookies, `.env`, perfis de Chrome,
dados sensíveis, arquivos de clientes ou evidências autenticadas.
Logs operacionais só devem ser consultados sob demanda em ambiente autorizado.
Não publicar repositório privado sem aprovação.

## Limites e alternativas

Não existe janela de contexto infinita: a ferramenta recupera apenas os
trechos necessários. Precisa acesso ao Git ou arquivos; uma conta diferente
não ganha acesso ao repositório automaticamente. O MCP local Basic Memory
é alternativa complementar, gratuita e open source, mas acrescenta
dependência; não precisa ser instalado para este sistema funcionar.


## Servidor MCP pronto para agentes compatíveis

Este repositório inclui `scripts/agent_memory_mcp.py`, um servidor
**stdio JSON-RPC 2.0** escrito apenas com a biblioteca padrão do Python.
Ele fornece:
- `dominium_memory_brief`: handoff do estado atual;
- `dominium_memory_search`: FTS5 com caminho da fonte;
- `dominium_memory_history`: commits recentes;
- `dominium_memory_record`: anotações curadas, sem dados privados;
- recurso `dominium://memory/current`: estado atual em Markdown.

`.mcp.json` contém a configuração de projeto para clientes compatíveis.
O comando executável é `python scripts/agent_memory_mcp.py`,
com diretório de trabalho na raiz do clone. Nenhum serviço web público
ou credencial é necessário. Clientes que exigirem configuração própria
podem apontar para o mesmo comando.

**Atenção:** o arquivo do projeto não concede automaticamente ferramentas
a todas as versões/interfaces de ChatGPT. Um cliente que não lê arquivos
ou não oferece MCP precisa de acesso explícito ao clone e/ou upload do
handoff. O primeiro uso de MCP pode pedir aprovação local.

## Referências oficiais e alternativa opcional

- Codex / AGENTS.md: https://learn.chatgpt.com/docs/agent-configuration/agents-md
- Claude Code / CLAUDE.md: https://support.claude.com/en/articles/14554000-claude-code-power-user-tips
- GitHub Copilot: https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/add-custom-instructions/add-repository-instructions
- Cursor: https://cursor.com/docs/rules
- SQLite FTS5: https://www.sqlite.org/fts5.html
- Basic Memory MCP local opcional: https://github.com/basicmachines-co/basic-memory

Conectores de memória terceirizados não substituem controle de
acesso, revisão de dados sensíveis ou Git como fonte da verdade.

## Handoff portátil sem conectar Git (troca de conta)

Execute `python scripts/agent_memory.py export`. A ferramenta cria
`output/dominium-agent-handoff.zip` contendo SOMENTE instruções,
memória curada, mapa de código e histórico compacto do Git. O ZIP não
inclui código-fonte, cookies, credenciais, perfis, bancos de dados ou
relatórios de clientes. Verifique a política de compartilhamento TECHNET
antes de fornecer o arquivo a terceiros.

Outra IA pode usar o ZIP como orientação inicial. Para editar o projeto,
ainda precisará do clone autorizado e dos ambientes/credenciais concedidos
explicitamente. Esse pacote não sincroniza alterações de volta ao Git:
após uma sessão externa, registre novas decisões no repositório original.

## Skills portáteis

- Codex/ambientes com Agent Skills: `.agents/skills/dominium-memory/SKILL.md`.
- Claude Code: `.claude/skills/dominium-memory/SKILL.md`.

As skills descrevem quando recuperar contexto e como registrar resultados.
Não substituem o código nem criam acesso automático a contas de terceiros.
