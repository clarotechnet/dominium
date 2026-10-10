# Progresso e evidências

- Fonte principal c13e5f0, worktree remoto `C:\DominiumLab\ui-desc-20261010`, branch `codex/ui-desc-20261010`; checkout principal preservado.
- Fundo original Claro/Technet em cimento incorporado sem alterações na imagem.
- Proxy Python com sessão DESC e CSRF privados no servidor; acesso restrito a admin/controller, ator vem da sessão Dominium.
- Testes proxy: 4 aprovados; leitor primário Atlas + fallback OCR: suíte DESC 44 aprovada. Frontend: 3 testes unitários aprovados antes da integração HTML.
- Serviço DESC atual trabalha em teste: aprovação é simulação, executor real bloqueado explicitamente. Não habilitar via rótulo.
- Leitor do grupo 120363411539759480@g.us permanece consulta; código existente reutilizado pela captura DESC.
- QA visual/navegação aprovado no desktop/celular e na atualização com JavaScript antigo em cache. Revisão independente concluída; horário de dados, tema salvo e cache corrigidos. Quality gate aprovado com 769 testes Python (22 pulados), suítes JS e build.
- Relay privado instalado em C:\DominiumRuntime\DescRelay-20261010, porta8793; consulta protegida devolveu modo teste e300lotes. Segredo de conexão somente no servidor e no segredo criptografado de deploy, fora de static/Git.
- Publicação Hostinger concluída no workflow38055577310, commit34c3b1e, branch codex/ui-desc-20261010. Fonte baseada na main atual c9a9bff, preservando melhorias anteriores.
- Leitor primário instalado com backup; teste Windows3/3 e suíte local44/44. Reinício Bot ainda pendente; nenhum envio de mensagens e nenhuma baixa real efetuados por este trabalho.
- Executor real permanece bloqueado no painel original. Preparar revisão/produção separadamente, com validação independente no Imperium; não declarar simulações como baixas.
- Runtime Python do servidor possui mudanças fora da main: instalar patch localizado; nunca substituir app.py completo pela main.
- WSL via execução remota foi bloqueado pelo Commander. Arquivos UNC acessíveis; reinício Bot deverá ocorrer pelo usuário caso continue bloqueado.

## Ajuste após prints — 10/10

CSS de rolagem, métricas e rodapé corrigido. Health suporta schemas Node/Python; inteligência indisponível exibe métricas não disponíveis. Vínculo autoritativo WhatsApp/recurso Imperium e leitor privado da OS implementados.430 com Atlas+contrato+OS/recurso independe conclusão/loginTOA/materials_complete;409 mantém regras. Nenhuma baixa real habilitada. Reinício Bot necessário para carregar módulos instalados.
