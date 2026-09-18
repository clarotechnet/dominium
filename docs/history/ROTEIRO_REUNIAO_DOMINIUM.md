# DOMINIUM — roteiro para a reunião

## Abertura em 40 segundos

> O DOMINIUM centraliza a operação de campo em uma tela: consulta e separa as OS, acompanha prazo e produtividade, cruza técnico com estoque e executa baixas no Imperium com validação e auditoria. O objetivo não é apenas acelerar clique; é reduzir baixa errada, impedir repetição de operação incerta e dar visão das quatro bases no mesmo padrão.

## Demonstração recomendada

1. Abra **Monitor de O.S.**.
2. Clique em **Cenários de exemplo**.
3. Mostre que o aviso amarelo deixa explícito que nenhuma OS real será alterada.
4. Passe pelas abas abaixo. Todas exibem quantidade e uma OS fictícia com selo **EXEMPLO**.

| Situação | Exemplo para mostrar | O que dizer |
|---|---:|---|
| Equipes | Rafael Nunes com 4 OS | Distribuição por técnico e leitura de carga. |
| Monitor geral | 8 OS | Em campo, pendente, concluída e cancelada em Natal, Fortaleza, Mossoró e Recife. |
| Em campo | 990070001 | Serviço ainda em execução, separado pelo status oficial disponível. |
| Pendentes | 990070003 | Serviço aguardando atendimento ou desfecho, sem inventar uma categoria de “quebra”. |
| Concluídas | 990070002 | Encerramento, código de baixa e observação preservados no mesmo registro. |
| Desconexão | 990070005 | Desconexão/retirada identificada pelo nome real do serviço. |
| Retorno de credenciada | 990070002 | Retorno concluído e separado automaticamente. |
| Revisitas | 990070002 | Revisita calculada pelo histórico do contrato, com atividade ofensora. |
| BAIXA 100 | 990070004 | OS encerrada com código 100. |
| Gestão de rotas | 7 rotas | Distribuição por cidade, bairro e node. |
| Capacidade técnica | 5 técnicos | Carga ativa e indicação de disponibilidade/atenção. |

Não apresentar **TEC1**, “Quebras” ou “Quebra técnica” como entregas do TOA. TEC1 depende de outra fonte oficial/indicador e não faz parte do pedido inicial de API. “Quebra técnica” não é um tipo de serviço oficial usado nesta demonstração.

## Sequência para apresentar ao Nathan em 12 minutos

1. **Problema operacional:** exportação é fotografia e ainda depende de alguém baixar/importar arquivo.
2. **Monitor de O.S.:** ativar **Cenários de exemplo** e mostrar Em campo, Pendentes, Concluídas, Desconexão e Retorno.
3. **Baixa completa:** explicar que código e observação não bastam; a OS precisa trazer equipamentos e materiais instalados/retirados, quantidade e serial.
4. **Troca:** mostrar a exigência de serial instalado + serial retirado na mesma OS.
5. **Estoque:** mostrar rastreamento do serial por técnico, bloqueio de divergência e miscelâneas por quantidade.
6. **Gestão:** produtividade, revisita, relatório por base, saúde das quatro bases e auditoria.
7. **Pedido à Claro:** autorizar o desenho de uma camada read-only filtrada, sem CPF, telefone ou endereço, começando por uma base e período definidos.

Critérios de sucesso do piloto:

- acompanhar o desfecho sem nova exportação manual;
- receber código de baixa e observação oficial;
- relacionar inventário instalado/desinstalado à OS;
- validar tipo, quantidade e serial sem dados pessoais do cliente;
- manter trilha de auditoria e impedir repetição após resposta incerta.

## O que já pode ser apresentado como entregue

- Filtro combinado de **Status + Tipo de Serviço**, incluindo desconexão e em campo.
- Monitor operacional com 11 visões, indicadores, busca, alertas locais e atualização automática quando o TOA está conectado.
- Importação automática do TOA; agenda atual configurada para **09:00, 14:00 e 17:20**, além da execução manual.
- Validação de duplicidade e escopo antes de importar OS.
- Rastreamento de serial por estoque/técnico e auditoria entre OS e equipamento.
- Dashboard de produtividade por técnico e por base.
- Relatório diário consolidado em PDF.
- Health check das bases Natal, Fortaleza, Mossoró e Recife.
- FlowScope local: lê capturas, reconstrói DataSnap e separa consulta, preparação, ação e escrita executada.

## O que depende da API oficial do TOA

- Alerta realmente proativo de OS pendente sem depender da sessão do navegador.
- Distribuição geográfica com coordenadas oficiais e atualização em tempo real.
- Sincronização nativa de equipes/placas e eventos push.

Frase recomendada:

> A arquitetura já está pronta para receber a API. Hoje usamos sessão autenticada e capturas autorizadas; quando o TOA liberar o acesso oficial, trocamos o conector sem refazer o painel nem as regras operacionais.

## Capturas novas — resposta correta

- A captura do Dalton confirmou consultas nas quatro bases, sem nova gravação de baixa.
- A captura do Renan confirmou o fluxo de estoque/equipamentos em Fortaleza e preparou métodos de `MovEstoque` e `OrdemServico`, incluindo campos ligados a equipamento duplo.
- Ela **não executou uma baixa completa**. Por isso o FlowScope agora mostra separadamente “escrita preparada” e “escrita executada”. A automação de serial duplo só deve ser liberada após uma captura autorizada de sucesso ponta a ponta.
- A captura do Felipera confirmou chamadas reais de `DspLocCodBaixaServico`, `DspValidarEquipInstalados`, `DspLocEquipContrato`, `DspSpTransfAutomaticaMiscelanea`, `DspInserirCodigoBaixaServico` e `DspBaixarMiscelaneasRomaneio`. Ela reforça que baixa, equipamento e miscelânea fazem parte do mesmo fluxo operacional.
- O pacote do Felipera possui arquivos auxiliares e uma cauda parcialmente zerados. As chamadas são evidência de fluxo, mas não devem ser apresentadas como comprovação isolada de sucesso ponta a ponta sem conferir a resposta final da OS.

## Segurança — resposta curta para a reunião

> A segurança fica fora da tela operacional. O painel aceita somente acesso local, rejeita origem cruzada e host falso, limita tamanho e frequência das requisições, não permite enquadramento da página, mantém um inventário interno das integrações e reduz dados sensíveis nos logs. A API oficial usa HTTPS, destino fixo, JWT, timeout e não repete baixa incerta. O navegador nunca recebe credenciais do Imperium ou acesso direto ao banco.

Não use “inquebrável” ou “100% seguro”. Use: **defesa em camadas, menor privilégio, destino autorizado, confirmação após incerteza e auditoria**.

## Perguntas que provavelmente virão

**“Isso pode baixar uma OS errada?”**
O fluxo valida OS, contrato, cidade/base, técnico, código e equipamento. Divergência bloqueia a ação e vai para revisão; uma resposta incerta é confirmada antes de qualquer nova tentativa.

**“O exemplo mexe na produção?”**
Não. O modo de demonstração é isolado, não baixa, não notifica e não exporta.

**“Funciona para todas as bases?”**
O painel já possui perfis separados para Natal/Parnamirim, Fortaleza, Mossoró e Recife, com saúde e relatório consolidados.

**“E se o TOA estiver fora?”**
O último retrato continua visível e é marcado como desatualizado. Filas persistentes aguardam a próxima consulta; não se transforma ausência de dado em baixa automática.

**“Qual o ganho?”**
Menos consulta manual repetida, menos erro de serial/código/base, menor retrabalho após timeout, rastreabilidade por OS e uma visão gerencial única da operação.

## Fechamento

> O ganho principal é padronizar decisão e execução. O operador continua enxergando e aprovando o que importa, enquanto o DOMINIUM faz consulta repetitiva, validação, fila, confirmação e auditoria. Assim a operação cresce para novas bases sem multiplicar o mesmo trabalho manual.
