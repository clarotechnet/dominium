# Dominium: novo visual e DESCONEXÃO

Objetivo: reformular todas as telas com os painéis transparentes, navegação compacta e transições da referência enviada, usando vermelho #ff1738, preto e a foto Claro/Technet em cimento enviada por Dalton. A operação continua usando os controles e APIs existentes.

## Interface
- Fundo de marca com camada escura; cartões elevados; menu e cabeçalho flutuantes; tipografia Archivo existente.
- Layout responsivo; tabelas continuam roláveis; foco visível; reduzir animações quando solicitado pelo sistema.
- Nova entrada DESCONEXÃO, URL #desconexao, com lista por contrato/técnico, filtros, fotografias, leitura OCR, evidência Atlas, equipamentos entrando/saindo, impedimentos e revisão.
- O modo real do serviço deve aparecer. Uma simulação nunca é rotulada como baixa confirmada.

## Integração
- O frontend usa /api/disconnection/* no mesmo domínio, sessão Dominium e CSRF existentes; não usa iframe, IP local ou PIN no navegador.
- O Hostinger valida a sessão e encaminha somente rotas permitidas por uma conexão privada para um relay dedicado. Esse relay usa o painel DESC existente em 127.0.0.1:8787. PIN e cookie da revisão permanecem no servidor, sem depender da ponte antiga do TOA. O app.py também suporta a mesma fronteira para instalações autenticadas locais.
- Fotos e dados de técnicos exigem perfil admin/controller; o aprovador vem da sessão autenticada.
- Atlas reutiliza consultarAtlasPorSeriais e o leitor existente do grupo 120363411539759480@g.us, com validação canônica adicional para baixa. Esse grupo de consulta não se torna um grupo de baixa.
- Janela por grupo/técnico/contrato de cinco minutos, sem reprocessar histórico antigo.

## Regras
- 430 exige equipamento retirado, sem miscelânea; nunca pegar inventário do cliente.
- 409 preserva o instalado da tarefa; não vira 430.
- Canonizar no serial em negrito do Atlas, conferindo contrato e tipo; múltiplos candidatos exigem conferência.
- EMBRATEL acima do primeiro contrato preenchido do histórico origina proposta 400.
- Manter OS e equipamentos separados. Evidência incompleta/offline não prova ausência de OS.
- A execução só pode usar o executor Imperium existente com confirmação independente; não habilitar a execução do painel de teste por trocar um rótulo ou flag.

## Verificação
Testar autenticação, rotas permitidas, fotografias, identidade do aprovador, indisponibilidade, navegação, filtros e acessibilidade; executar o quality gate antes de deploy. Validar o fluxo instalado e preservar backups e alterações locais.
