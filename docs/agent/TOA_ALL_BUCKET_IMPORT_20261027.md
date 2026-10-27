# Importação dos 13 buckets DMV — 27/10/2026

Pedido do usuário: importar todos os buckets, incluindo adesão, para preparar um teste de baixa produtiva.

## Instalado e verificado

Runtime efetivo: `C:\DominiumRuntime\Imperium\FerramentaImperiumDireto-OLLAMA`.
Instalação 09:52:57 America/Sao_Paulo, backup `backups/import-all-buckets-20261027-095257`.
Os seis hashes instalados conferem com o pacote `deploy/server-import-all`.
Painel e gateway reiniciados quando ociosos; Chrome e perfil preservados.
O estado habilitado do worker existente foi restaurado.

O agendador passa a percorrer os 13 buckets descobertos das cinco praças.
O novo endpoint local `/toa/import-export` permite somente esses buckets e a data do dia.
O caminho anterior `/toa/export`, o coletor DESC e `desc_only_scope.py` permanecem restritos a desconexão.
O novo filtro de importação aceita os serviços de adesão, mantendo as exclusões de data,
identidade inválida e duplicidade no arquivo. A validação vigente de cidade/perfil e
a reconciliação de O.S. presentes no Imperium são preservadas.

Baixas não foram ampliadas: API real confirmou `service_type_filter=disconnection` no
worker existente após o restart. Importar adesão não valida nem executa sua baixa produtiva.

## Validação

- 11 testes específicos: escopo de 13 buckets, inclusão de adesão, limites de data/rota,
  exclusões de identidade/duplicidade, agendador completo, reconciliação e preservação DESC.
- 5 verificações do novo filtro no Windows e 28 testes legados de TOA no servidor aprovados.
- Gate final local: 958 testes Python, 22 ignorados, JavaScript, Ruff e build/auditoria aprovados.
- O ambiente de teste local inicialmente não possuía websocket-client, Selenium e Ruff;
  dependências de teste foram instaladas em scratch, sem alteração das dependências de produção.

## Rodada operacional

Solicitação manual autorizada às 09:53:24, diretório privado de fontes
`logs/toa-exports/20261027/095324`. Nenhum CSV ou dado de cliente foi versionado.

Rodada concluída às 10:03:26: 13 buckets, 1.264 registros elegíveis,
799 importações confirmadas, 427 já existentes/reconciliados, 38 sem confirmação.
Outros 67 registros foram excluídos pelas validações, sem envio.

| Praça | Importadas | Existentes/reconciliadas | Sem confirmação |
| --- | ---: | ---: | ---: |
| Fortaleza | 240 | 110 | 9 |
| Recife | 181 | 106 | 7 |
| Mossoró | 9 | 25 | 2 |
| Natal | 329 | 154 | 7 |
| Parnamirim | 40 | 32 | 13 |

Não confundir retorno `ok` do protocolo com confirmação de todas as O.S.
As 38 pendências têm sete serviços sem correspondência, 18 confirmações ausentes
e 13 respostas legadas não interpretadas. Evitar reenvio sem consulta ao Imperium.
JCR-DMV_VT estava vazio. As 13 de PWM-DMV_VT ficaram sem confirmação e não foram reenviadas.

Confirmado durante a rodada: os novos buckets de Fortaleza importaram 220 O.S.;
adesão está presente nos registros confirmados. Há retornos parciais do protocolo
legado e serviços sem correspondência, que não devem provocar reenvio cego.

## Código e recuperação

Pacote preservado no branch `maintenance/import-all-buckets-20261027`, commit inicial
`b53319eefb545ae2f60ff06bffdffa47e8e4ce52`. A instalação foi feita no runtime legado;
não confundir este pacote com substituição integral pelo app.py da branch principal.

O instalador confere âncoras e sintaxe antes de escrever e salva os arquivos anteriores.
Revisão independente encontrou uma corrida no script inicial de reinício online.
O script reutilizável `deploy.py` foi alterado para instalação exclusivamente offline:
recusa portas 8765/9341 abertas e não contém encerramento de processo. Antes de utilizá-lo,
parar painel/gateway e seus supervisores somente quando ociosos. Dois testes reais de socket
verificam o bloqueio. A instalação inicial desta rodada não teve importação concorrente.
Para recuperação, restaurar os cinco arquivos alterados a partir do backup e reiniciar
somente painel/gateway ociosos. O arquivo novo `toa_import_scope.py` pode permanecer
sem uso ou ser removido após restaurar os consumidores. Preservar Chrome e fontes CSV.

Próximo passo: selecionar uma única adesão concluída no TOA, confirmar sua O.S., cidade,
técnico, equipamentos e materiais no Imperium e executar a preparação da baixa produtiva.
Não habilitar baixa de adesão em lote a partir desta mudança de importação.
