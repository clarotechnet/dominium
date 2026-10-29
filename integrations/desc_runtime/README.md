# Runtime DESC do servidor TECHNET

Estes módulos pertencem ao runtime legado Windows/WSL, separado do aplicativo web.
Não copiar `app.py` nem `imperium_api.py` completos do web para o servidor:
as versões têm diferenças operacionais que precisam ser preservadas.

## Origem e instalação

- Python: `C:\DominiumRuntime\Imperium\FerramentaImperiumDireto-OLLAMA`.
- Bot: `/home/technet/BotDMV/src` no Ubuntu/WSL.
- `disconnect_local_runner.py`, `nightly_backlog_106.py` e
  `whatsapp_bridge_service.py` são fontes versionadas do runtime.
- `adm_allocation.py` e `toa_adm_task_splitter.py`, na raiz do repositório,
  precisam acompanhar o runner no mesmo diretório do runtime.
- `bot/disconnectPilot.js` e `bot/disconnectPilotCoordinator.js` documentam
  o coordenador existente. O parser trata candidatos de 7–9 dígitos; o TOA
  precisa confirmar contrato, grupo, responsável, atividade e bucket.
- `patch_runtime_safety.py` contém transformações cirúrgicas para o preparo
  de materiais e o plano oficial legados. Não é instalador: validar hashes,
  compilar, testar em staging e salvar backups antes de substituir fontes.

Não versionar configuração privada, filas, mensagens, fotos, credenciais
ou arquivos dos grupos. Os exemplos novos de mensagens usam dados fictícios.

## Travas obrigatórias

- Executor geral, produtivas gerais e execução direta de grupos continuam
  desativados até homologação.
- **Exceção autorizada em 29/10/2026: lote 106 diário às 23h de Brasília.**
  Somente O.S. em campo do próprio dia, filtro desconexão/retirada, quatro
  cidades, DataSnap, sem itens. O agendador é do servidor e não depende do
  navegador. Recibo exclusivo por IdOS impede repetição após envio incerto.
- Lote 106 pode repetir somente GET ocupado (409), até 12 tentativas com
  pausa de 15 segundos, dentro da janela autorizada. POST nunca é repetido.
- DESC: sem miscelâneas. Uma única O.S. recebe equipamentos por código.
  **Múltiplas O.S. continuam bloqueadas para execução:** falta homologar o
  fechamento das demais O.S. sem duplicar equipamentos. O plano já lista o
  dono das movimentações e as acompanhantes.
- API oficial: falta de qualquer material bloqueia antes da transferência;
  assinatura e INST GPON - INST CABO aceitam apenas código de baixa.

## Testes

O quality gate executa os testes portáveis de mensagem, alocação, extração
de tarefas, agendador 106 e caixa de mensagens. Os testes de integração
do runner exigem as dependências legadas do servidor e são executados em
staging, com I/O de escrita simulado. Nunca executar um lote real como teste.

No staging com os módulos legados disponíveis no `PYTHONPATH`:

```powershell
python -m unittest test_desc_sector_scope test_desc_multi_owner_runtime test_runtime_official_materials -q
node --test test_desc_message_formats.cjs
```

O agendador ativo pode ser consultado em `GET /api/nightly-backlog` no
serviço local 8765. Ativação não comprova que o lote das 23h já foi executado.

Detalhes e limites: `docs/agent/memory/DESC_ADESAO_REVALIDACAO_20261029.md`.
