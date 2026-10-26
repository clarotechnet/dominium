# Fortaleza — rechecagem operacional 26/10/2026, 00:54–00:55

Fuso America/Sao_Paulo. Fortaleza validada novamente no servidor e no DOMINIUM autenticado. A meta específica de Fortaleza pode ser encerrada; a meta das quatro cidades permanece incompleta.

## Evidências atuais

- Servidor DESKTOP-K7J3E1N online; SQLite aberto exclusivamente em mode=ro, integrity_check=ok.
- Filas históricas 276868465 e 276868467: attachment_wait, zero linhas; downloads Chrome/CDP sem cache, credenciais da sessão, HTTP404/success=false em ambas.
- Nova fila Fortaleza 276907771, criada em execução anterior autorizada: ready, 29.529 linhas persistidas. Download do anexo anunciado Chrome/CDP HTTP200/success=true.
- Fonte privada reinterpretada integralmente e comparada a query_rows: igualdade das 29.529 linhas.
- Exportações do relay real, com autenticação e operador proprietário: CSV200 e XLSX200; formatos comparados célula por célula, 29.529 linhas mais cabeçalho, ZIP íntegro e nenhuma fórmula.
- SHA-256 CSV: 0cc396ac0bbbb535b9ca0af4dbbb8e9880d28c20c13ad5bf8e071892433e4cd2, igual ao download de navegador e à fonte documentados na verificação anterior.
- Cloud Browser autenticado: Recursos → Pendente → Fortaleza, principal276907735/reserva276907771, “QUERY disponível para consulta”, 29.529 equipamentos, exportações habilitadas.
- Após recarga, nova abertura de Pendente recuperou a mesma família, tabela com11 colunas e linhas1–100 de29.529; nenhuma nova QUERY enviada.
- Consulta não enviou geração, recuperação, baixa, transferência, movimento de estoque ou operação TOA, nem reiniciou Chrome/relay.

## Preservação e limites

- Relatórios históricos: Natal276868277/20.179, Recife276861849/55.807 e Mossoró276855582/893 preservados.
- Relatórios recentes: Recife276907778/55.749 e Mossoró276907784/892 continuam ready por contagem direta SQLite.
- Banco observado com20 trabalhos; família Natal276908463/276908572 aparece attachment_wait, sem linhas. Esta execução não criou esses IDs nem testou seus anexos; não atribuir a eles resultado atual de rede apenas pelo estado do banco.
- O registro ATLAS_QUERY_VERIFICATION_20261026.md documenta seis IDs anteriores de Natal com anexo404. Não declarar as quatro cidades concluídas.

## Implementado / testado / publicado

- Implementado nesta execução: somente diagnóstico temporário e este registro; nenhum patch operacional.
- Testado nesta execução: downloads dos três IDs Fortaleza acima, parser versus banco, exportações reais, UI autenticada e persistência após recarga.
- Uma primeira sondagem de diagnóstico não inicializou a conexão Chrome e retornou AttributeError; corrigida apenas no script temporário. Repetição completa confirmou404/404/200, exit code0. Nenhum defeito do produto inferido desse erro.
- Publicado anteriormente: recuperação controlada c94984b; não realizado novo deploy nesta execução.
- Publicado agora: somente este registro, sem dados pessoais, credenciais ou URLs privadas.
- Pausar o acompanhamento específico “Concluir QUERY de Fortaleza” após registro desta evidência. O worker do servidor é independente; não será parado. Natal permanece pendente em sua investigação própria.
