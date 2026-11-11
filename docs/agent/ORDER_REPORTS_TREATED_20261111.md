# Relatórios de OS — versões bruta e tratada (11/11/2026)

## Interface
Em Relatórios de OS, cada card oferece duas ações:
- Vermelho: Baixar Bruto · XLSX (mesma URL, conteúdo e 42 colunas originais).
- Cinza: Baixar Todos · Tratado ou Baixar Manutenção · Tratado.

A exportação tratada usa o mesmo GET somente leitura com parâmetro fixo
`&variant=treated`. A política de Hostinger/Worker e a rota Python aceitam
somente esse valor adicional. As restrições de cidade, período, acesso, limite
e concorrência permanecem iguais.

## Macro Vistoria_Supervisores / Todos os serviços
- Reorganiza as colunas originais na ordem F, J, P, N, AC, AD, R, S, Y, Z, AA
  (11 colunas). Remove as demais e aplica larguras legíveis.
- Remove contratos duplicados (coluna original J), conservando a primeira
  ocorrência, **antes** de filtrar por código de baixa.
- Mantém códigos 108, 206, 205, 303, 305, 110.
- A macro original apenas ocultava linhas com AutoFilter; o relatório tratado
  contém apenas as linhas correspondentes (o bruto continua completo).

## Macro Rev_Imperium / Manutenção — corrigida após comparação com Excel real
- Exclui registros com Número W.O (K) vazio.
- O filtro Excel seleciona os seis tipos abaixo e a sequência de exclusão
  **remove esses registros selecionados**, conservando os demais serviços:
  MANUTENCAO CORRETIVA - DEGRADACAO MDU;
  MANUTENCAO CORRETIVA - MDU;
  MANUTENCAO PREVENTIVA - MDU;
  MANUTENCAO PREVENTIVA INDOOR;
  SUBSTITUICAO DE CONTROLE REMOTO ANALOGICA;
  TROCA DE EQUIPAMENTO STREAMING.
- Preserva as 42 colunas. O código antigo fazia o inverso, mantendo apenas
  os seis serviços (erro de interpretação da macro).
- O bloco `Rows("16:1048576")` é uma seleção gravada do Excel, não
  um limite funcional de 15 linhas. Não truncar linhas 16 em diante.
- Validação somente leitura de Natal em 10/11/2026: bruto 80 registros;
  3 registros de TROCA DE EQUIPAMENTO STREAMING excluídos;
  XLSX VBA fornecido pelo operador com 77 registros, sem filtro ativo;
  conjunto de 77 números de OS coincide integralmente por SHA-256 do
  conjunto ordenado (sem armazenar dados operacionais no GitHub).


## Testes
Executar em worktree isolada:
`python -m unittest tests.test_order_reports tests.test_order_reports_treated`
`node tests/test_order_reports_ui.cjs`
`node --test integrations/import_bridge/order_reports.test.mjs`

## Implantação e rollback
1. Fazer backup do order_reports.py e do estado atual do relay DESC na porta 8793.
2. Atualizar somente order_reports.py no runtime complementar do relay.
3. Publicar o Worker existente com wrangler.jsonc e seus bindings preservados.
4. Publicar Hostinger através do fluxo de deploy já existente na main.
5. Verificar antigo GET bruto, novo GET tratado, autorização 403 viewer,
   MIME e XLSX válido, sem escrever nenhuma O.S.
6. Rollback: restaurar order_reports.py original, versão anterior do Worker
   e commit Hostinger anterior, sem alterações em dados operacionais.

**Atenção:** deploy em qualquer um dos três componentes isoladamente pode
deixar os botões tratados indisponíveis até o restante estar atualizado.
