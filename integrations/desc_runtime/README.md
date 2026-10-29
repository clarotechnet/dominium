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

## Releitura de movimentos persistidos (29/10/2026)

A API legada recebeu correção **somente de leitura** em quatro métodos:
`_parse_installed_detail_row`, `_find_installed_detail_serial`,
`_parse_removed_detail_row` e `read_detail_equipment_movements`.
O GetRecords do Imperium grava flags e trailers distintos dos dados enviados
na baixa; não usar a ausência de movimentos no leitor antigo como prova de
ausência de movimentação. A validação cruza IdOS, técnico, vínculo de registro,
serial repetido e rejeita duplicatas. Nenhuma rotina de envio ou estoque foi
modificada por este patch.

Regressão portável, com registros fictícios e leitor legado congelado:

```powershell
python -m unittest -q integrations.desc_runtime.test_persisted_removed_movements
```

**Servidor:** staging `C:\DominiumRuntime\Maintenance\DescRemovedReader-20261029`.
Instalação cirúrgica do arquivo `imperium_api.py` com hash anterior
`a0f45197e42d872ea4f824ce4abf33d2800f8d9c753623f85880eb171aab3ccf`
e novo
`61045717b6d7ccfd672088ee2c81fc0510ddedb79fa052ea3650501cd85cdf0e`.
Backup recuperável:
`C:\DominiumRuntime\Backup\DescRemovedReader-20261029-163756\imperium_api.py`.
O instalador local registra `installed.json` e aceita `rollback`, seguido
de reinício verificado da porta 8765. Os 15 testes específicos passaram antes
da recarga e a porta voltou saudável; lote 106 às 23h preservado, sem
ativar executor geral.

Os casos reais de validação por releitura foram O.S. 2603550706 (430,
retirada C85D38D7FAED) e 2614498305 (409, instalação 241806484254 e
retirada 241800890005), ambos Recife. **Não reenviar essas baixas.**
Isso não homologa o fechamento acompanhante de múltiplas O.S. nem a
Adesão completa pela API oficial. Referência detalhada:
`docs/agent/memory/DESC_ADESAO_REVALIDACAO_20261029.md`.

## BotDMV e !parcial — manutenção de 29/10/2026

- As mensagens espontâneas `Consulta TOA · desconexão` foram **silenciadas**
  no `index.js` do BotDMV em produção; a captura/consulta interna permanece.
- O `!parcial` voltou a executar o Python Windows após restauração do registro
  `WSLInterop`. Unit de recuperação para próximos boots:
  `integrations/desc_runtime/dominium-wsl-interop.service`.
- Teste de 4 bases com renderização de 4 PNGs via socket simulado passou.
- Uma O.S. **RETIRADA FORA TOA** manual de Natal foi fechada e relida com
  exatamente um decoder e um smart retirados na mesma baixa 430. Não repetir.
- Detalhes, evidências, limitação de testes e localização do recibo privado:
  `docs/agent/memory/BOT_PARCIAL_MANUAL_NTL_20261029.md`.
