# DOMINIUM — Controle de baixas: fila animada por cidade

**Registro:** 06/11/2026. **Branch:** `feat/controle-baixas-homolog-20261106`. **Estado:** interface de homologação, sem chamadas TOA ou baixas.

## Correção de escopo

A visualização de **quatro cidades pertence exclusivamente ao Controle de baixas**, NÃO à Análise Backlog.

- **Controle de baixas:** O.S. de Natal/Parnamirim, Fortaleza, Recife e Mossoró, com a fila de trabalho, erro e confirmação no Imperium.
- **Análise Backlog:** origem Claro, cruzamento com histórico Imperium e Fora de Rota. **Nenhuma alteração funcional** nesse módulo nesta revisão.
- A tentativa anterior de adicionar `backlog-claro-board.*` foi desfeita; os arquivos foram retirados da branch.

## Fila visual por cidade

A separação entre estado operacional e estado visual é explícita.

1. **Em tratamento:** a O.S. ativa fica na primeira posição, no topo da cidade.
2. **Erro:** a O.S. desce para a área de revisão humana, abaixo da O.S. ativa; os erros mais recentes aparecem antes dos anteriores, que descem.
3. **Confirmada:** só entra no histórico depois de confirmação positiva do Imperium; fica abaixo das O.S. pendentes e com erro.
4. **Aguardando:** somente atividades elegíveis na janela e importadas podem entrar em tratamento. Pendente/em rota é consultada após 30 min; iniciada em 15, 20, 30 min, mantendo 30.
5. **Divergência/incerteza:** fica para revisão, sem reenvio automático.
6. A lista movimenta os cartões com técnica **FLIP**, animação de cerca de 460 ms, somente quando muda posição. Com preferência de movimento reduzido, a animação é omitida.

**Importante:** nenhuma dessas transições é acionada pela API real nesta etapa. O protótipo possui botões de **simulação exclusivamente com O.S. fictícias**: Próxima O.S., Erro e Baixa confirmada. Em modo de dados já carregados do Imperium esses botões somem.

## Integração futura

O backend autorizado precisará publicar eventos com IDs de O.S. e contrato, cidade, data/hora e estado de trabalho. Eventos de confirmação devem apontar para evidência de baixa no Imperium. Persistir histórico e tentativas para não perder a ordem da fila ao atualizar a página ou reiniciar o processo.

Atribuição de cidade não pode usar "Todos" como localidade. Uma O.S. sem cidade comprovada continua sem classificação.

A interface **não** controla a ordem real de execução no backend, não executa `GET` ao TOA e não executa `POST` ao Imperium. Preserva todos os bloqueios para Adesão e PROD enquanto a homologação de negócio está pendente.

## Verificação e deploy

- `node --test tests/test_close_control_city_board.cjs tests/test_close_control_engine.js`: aprovados.
- Testes de regressão do Backlog e semiautomática: aprovados.
- Chrome headless: capturas do cenário inicial, erro e baixa confirmada, executadas somente no computador de homologação.
- Acesso local: `http://127.0.0.1:8878/controle-baixas-smoke-preview.html` no PC de trabalho.
- Código em PR do DOMINIUM; **não publicado na Hostinger**.
- Os arquivos `smoke_*.png`, `animacao_*.png`, perfis do navegador e geradores de preview local são temporários; **não versionar**.
- O Worker da Claro e o módulo Análise Backlog existente continuam separados desta funcionalidade.
