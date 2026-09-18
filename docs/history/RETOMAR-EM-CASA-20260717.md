# Checkpoint para retomar em casa

Data da pausa: 17/07/2026

## Estado do projeto

- Ultima bateria concluida antes das capturas novas: 57 testes passando.
- Painel unificado estava funcionando em `http://127.0.0.1:8765`.
- O servidor foi encerrado antes da retirada do SSD.
- Nenhuma OS real foi criada ou baixada durante a analise das capturas novas.

## Captura 1

Arquivo original:

`Gravador-Imperium-Equipe-v1.0.1/Capturas/imperium-20260717-171528-DESKTOP-R285TSA-dalton-Mais-de-uma.zip`

SHA-256 do ZIP:

`7F6550DA22A628316C150A83DBD8BD901FDBBEEA4394E6C561AEE5F1E2D682BF`

Extraida em:

`diagnostics/captures/ftz-create-409-706-dalton-20260717`

Confirmado ate agora:

- Porta 579, Mossoro, mensagem 58: criacao nativa de OS `ENVIO DE CHIP VIA TECNICO`.
- Porta 579, Mossoro, mensagem 78: baixa `706`, ID interno 321, descricao `CHIP ENTREGUE`.
- Porta 596, Fortaleza: varias criacoes nativas de `RETIRADA FORA TOA` e baixas 430 foram capturadas.
- Porta 212, Natal: duas criacoes nativas de `RETIRADA FORA TOA` e baixas 430 foram capturadas.
- Os resumos estruturados por porta foram salvos como `operations-212.json`, `operations-596.json`, `operations-579.json` e `operations-599.json` na pasta da captura.

## Captura 2

Arquivo original:

`Gravador-Imperium-Equipe-v1.0.1/Capturas/imperium-20260717-174357-DESKTOP-R285TSA-daltoon-Mais-de-uma.zip`

SHA-256 do ZIP:

`912F67468C56973273FD2568E9A8C9E02E499C7E65608539A6F622A300F262BB`

Extraida em:

`diagnostics/captures/terminal-409-dalton-20260717`

Situacao:

- ZIP extraido e integridade conferida.
- Analise por porta ainda nao executada.
- Esta deve ser a captura principal para isolar o 409 do serial `1041213954D0`.

## Problemas para resolver na retomada

1. Analisar a captura 2 nas portas 212, 596, 579 e 599.
2. Corrigir a validacao do serial `1041213954D0`.
   - O painel classificou como EMTA, mas rejeitou o tipo.
   - O Imperium localizou o serial como codigo `41001518`, equipamento `TERMINAL DOCSIS 3.1 WIFI HI3120`, e concluiu a baixa 409.
   - Ajustar a classificacao para reconhecer equipamentos com nome `TERMINAL DOCSIS` como EMTA/modem.
3. Mapear e implementar o codigo 706 com equipamento instalado.
   - Confirmado na captura 1: ID 321 e descricao `CHIP ENTREGUE`.
4. Substituir ou complementar a criacao em massa via importador TOA pelo fluxo nativo capturado.
   - O importador ainda pode expirar sem criar a OS.
   - Parametrizar contrato, numero da OS, servico, tecnico, data e endereco ficticio no pacote nativo.
   - Validar primeiro em Fortaleza e Mossoro, que aparecem na captura 1.
5. Manter a protecao contra duplicidade e a confirmacao por consulta apos resposta incompleta.
6. Renomear o produto para `DOMINIUM` no topo do painel.
7. Frase proposta para o cabecalho:

   `Do primeiro comando ao ultimo registro, toda a operacao sob um unico dominio.`

   Alternativa mais curta:

   `Controle absoluto sobre cada ordem, estoque e movimento.`
8. Recife continua sem captura de baixa produtiva com transferencia de miscelanea. Nao habilitar transferencia automatica fora de Natal sem captura e validacao.

## Comandos para retomar

Executar os testes:

```powershell
py -3 -m unittest discover -q
node --check static\app.js
```

Iniciar o painel:

```powershell
py -3 -u app.py --port 8765
```

Analisar a segunda captura:

```powershell
py -3 diagnostics\extract_team_operations.py diagnostics\captures\terminal-409-dalton-20260717\imperium-20260717-174357-DESKTOP-R285TSA-daltoon-Mais-de-uma.pcapng --port 212
py -3 diagnostics\extract_team_operations.py diagnostics\captures\terminal-409-dalton-20260717\imperium-20260717-174357-DESKTOP-R285TSA-daltoon-Mais-de-uma.pcapng --port 596
py -3 diagnostics\extract_team_operations.py diagnostics\captures\terminal-409-dalton-20260717\imperium-20260717-174357-DESKTOP-R285TSA-daltoon-Mais-de-uma.pcapng --port 579
py -3 diagnostics\extract_team_operations.py diagnostics\captures\terminal-409-dalton-20260717\imperium-20260717-174357-DESKTOP-R285TSA-daltoon-Mais-de-uma.pcapng --port 599
```

## Retomada concluida em 18/07/2026

- Captura final analisada nas bases relevantes.
- Codigo 706 implementado para Natal e Mossoro, com serial parcial de chip.
- `TERMINAL DOCSIS` e `TERMINAL GPON` reconhecidos como EMTA.
- Criacao em massa substituida pelo provider nativo do Imperium.
- Pacotes nativos de Natal, Fortaleza e Mossoro reconstruidos byte a byte.
- Servicos habilitados somente onde houve captura valida:
  - Natal: `RETIRADA FORA TOA`, `CORRECAO ESTOQUE`, `ENVIO DE CHIP VIA TECNICO`.
  - Fortaleza: `RETIRADA FORA TOA`.
  - Mossoro: `ENVIO DE CHIP VIA TECNICO`.
  - Recife: criacao nativa desabilitada ate nova captura.
- Cada escrita nativa e enviada uma unica vez e confirmada por nova consulta do contrato.
- Interface envia o ID real do tecnico e aceita apenas contratos com sete digitos.
- Produto renomeado para `DOMINIUM`.
- Suite final: 67 testes passando; JavaScript sem erro de sintaxe.
- Smoke test visual: tela e confirmacao de criacao abertas sem erros no console.
- Consulta real somente leitura do contrato `4229178` validou o parser de cliente e endereco.
- Nenhuma OS foi criada ou baixada durante esta retomada automatizada.
