# BotDMV — silenciar respostas TOA, recuperar !parcial e baixa manual nativa (29/10/2026)

## Regra solicitada

O bot deve **continuar recebendo contratos e realizando consultas internas**, mas
não deve publicar respostas automáticas do tipo "Consulta TOA · desconexão"
quando o TOA estiver pendente, nem enviar essas consultas espontaneamente
aos grupos. Comandos solicitados expressamente pelo operador continuam ativos.
Isso **não é** autorização para reativar baixas DESC produtivas por grupos.

## Ajuste implantado no servidor (BotDMV / Ubuntu WSL)

Arquivo em produção: `/home/technet/BotDMV/index.js`, instância PM2 `Bot`.
Na chamada de `createDescPoolReplies`, foi alterada somente a condição:

```js
notificationsEnabled: () => false, // nenhuma resposta automática aos grupos
```

O coletor `descPoolReplies.capture`, a consulta interna `lookupReviewBatch` e
`descReview.captureMessage` foram preservados. A fila histórica permanece no
armazenamento privado do bot. Backup local com prefixo
`index.js.bak-disable-desc-pool-notifications-20261029-` no diretório do BotDMV.
PM2 reiniciado, processo online. Executados 7 testes em
`tests/toa-pool-replies.test.js`, todos aprovados; `node --check` aprovado.
Não enviar mensagens de teste a grupos reais.

A árvore completa do BotDMV não é uma cópia do aplicativo web: a alteração
cirúrgica foi aplicada diretamente ao servidor, não substituir o index.js
do bot por um módulo da branch main.

## Correção do !parcial (quatro Imperiums)

Erro observado: quatro respostas "Falha ao consultar o DataSnap" em um
`!parcial`. Causa confirmada: o WSL tinha `binfmt_misc` ativo, mas não tinha
a entrada `WSLInterop`, logo o processo Node não conseguia iniciar
`/mnt/c/.../.venv/Scripts/python.exe` (`Exec format error`). A consulta
DataSnap do Windows em si não estava comprovadamente indisponível.

Corrigido sem reiniciar a distro:
```sh
printf ':WSLInterop:M::MZ::/init:PF' > /proc/sys/fs/binfmt_misc/register
```

Persistência para próximos boots do Ubuntu por serviço systemd
`dominium-wsl-interop.service` (fonte versionada neste repositório),
instalado em `/etc/systemd/system`, habilitado via
`systemctl enable`. O unit só registra quando a entrada ainda não existe.
O ambiente do processo PM2 também foi atualizado para o socket estável
`WSL_INTEROP=/run/WSL/2_interop` e salvo com `pm2 save`.

Provas sem disparo ao WhatsApp:
- `probe_windows_parcial.js`: retorno JSON completo da base Fortaleza, exit 0.
- `parcialAllProfiles.integration.test.js`: 4 consultas DataSnap completas,
  4 páginas PNG válidas, consolidado calculado; teste aprovado com socket
  WhatsApp simulado (29/10/2026).
- O módulo `src/handlers/parcialHandler.js` não precisou de alteração.
- Não foi feito teste de reinicialização total do WSL porque derrubaria o bot.

## Baixa manual sem TOA — serviço RETIRADA FORA TOA

Uma ordem manual nativa de Natal não aparecia em
`/api/orders` porque o parser de uso geral trata principalmente números
convencionais de O.S.; o leitor `parcial_datasnap.parse_orders_for_partial`
já reconhecia a ordem nativa com número composto. A consulta DataSnap
com `status=field` encontrou a única ordem do contrato e seu técnico.
O serviço exato era `RETIRADA FORA TOA`.

A operação autorizada pelo usuário:
- pré-validação de identidade da O.S. e do técnico no detalhe DataSnap;
- pacote de **um** fechamento 430 com exatamente **duas retiradas**,
  um decoder e um smart card, zero instalações, zero miscelâneas;
- pacote produzido primeiro offline, sem I/O de escrita;
- **um único envio** por `ImperiumAPI.close_productive`;
- retorno positivo e confirmação independente por GetRecords: O.S.
  `CONCLUÍDA`, código `430`, exatamente dois seriais distintos retirados;
  ausente da lista em campo.

Os identificadores operacionais completos, recibo de envio e relatório da
consulta estão **somente no servidor**, em
`C:\DominiumRuntime\Maintenance\manual-close-natal-*.json` e scripts
`*_2870712.py`; não versionar dados de clientes nem identificadores de
equipamentos num repositório público. **Nunca reenviar este fechamento.**

## Segurança e limitações

Verificação final em `127.0.0.1:8765`: lote 106 às 23h de Brasília
`enabled=true` e `server_scheduler_active=true`; automações improdutivas
gerais `enabled=false`. O teste individual manual 430 não homologou a
baixa automática DESC com múltiplas O.S. nem a Adesão via API oficial.
A execução real do lote 106 da noite requer conferência após o horário.
