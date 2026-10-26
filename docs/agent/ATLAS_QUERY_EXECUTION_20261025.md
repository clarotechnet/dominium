# QUERY Atlas — execução e bloqueio atual em 25/10/2026

Verificação iniciada às 23:30, America/Sao_Paulo. Meta **não concluída**.
Este checkpoint substitui restrições históricas de geração nos registros anteriores.

## Autorização vigente

O usuário autorizou gerar novas QUERYs quando necessárias à investigação e à
validação atual de Fortaleza, Natal, Recife e Mossoró. A proibição antiga de
uma terceira fila de Fortaleza não vale mais. Registrar cada ID confirmado,
preservar idempotência e não repetir uma submissão de resultado incerto.
Não executar TOA, baixas ou alterações de estoques, contratos e O.S.
Não reiniciar o Chrome autenticado sem necessidade comprovada. Fazer backup
antes de alterar arquivos operacionais ou o banco.

## Evidência atual, distinta do histórico

- Remote Desktop Commander confirmou DESKTOP-K7J3E1N online. Relay Python
  escuta exclusivamente em 127.0.0.1:8793, PID 13180, iniciado em 24/10 16:04.
  Listener e respostas da interface não bastam para declarar worker saudável.
- Chrome gerenciado existente contém NetHome e uma guia Sign-on Único.
  `ChromeAtlas.open()` para o formulário de geração retornou
  `AtlasAuthRequired: Sessao Atlas precisa de login`. Não havia formulário de
  relatório nem controles de geração disponíveis. Nenhuma geração foi enviada.
- `evaluate_query()` dos IDs 276868465 e 276868467 retornou RuntimeError de
  formulário não carregado. A página NetTask foi encontrada, sem FilasForm,
  sem inputs e com sinais de autenticação/erro. Não foi possível reconfirmar
  COMPLETO, movimentos, parâmetros ou anexos anunciados atualmente.
- Os links XLS já persistidos dos dois IDs retornaram HTTP 404 pelo Chrome/CDP,
  sem cache. Esta execução não comprova sessão Atlas válida no momento do GET;
  não confundir este resultado com a navegação autenticada histórica.
- Preflight final às 23:41 confirmou novamente AtlasAuthRequired e uma mensagem
  explícita de sessão expirada no formulário de geração, sem enviar relatório.
- Banco operacional: 8 trabalhos, Fortaleza sem linhas, 33 falhas de anexo por
  fila e `attachment_wait / atlas_auth_required`. Últimas atualizações de
  Fortaleza observadas: 25/10 22:51. Não afirmar retry saudável apenas pela
  presença de uma data de próxima tentativa.
- Cloud Browser: login DOMINIUM concluído pelo formulário seguro; perfil
  administrador confirmado. Recursos → Pendente → Fortaleza → Consultar fila
  mostrou principal 276868465, reserva 276868467, horários, aviso de sessão
  Atlas expirada e CSV/XLSX desabilitados. Após atualizar a página, a cidade,
  ambos os IDs e o aviso voltaram a carregar do servidor.

## Comparação de versões

- GitHub main no início: `2be97dee2cb1fa965c34150584115f24cb24cf0b`.
  Checkout de publicação do servidor: `645728e5f93448cd6da10a48527588004b0a2135`.
  Os commits intermediários consultados alteram documentação.
- Os quatro arquivos operacionais `atlas_query_report.py`,
  `atlas_query_pipeline.py`, `atlas_query_http.py` e `atlas_query_data.py`
  coincidem em SHA-256 com o código atual de main. A revisão relevante mais
  recente da integração é `fea43ba`, incluindo download nativo para arquivos
  grandes. Não há necessidade demonstrada de outra API ou serviço.
- Frontend de produção respondeu HTTP 200 e SHA-256
  `1fbef678842616abcf8a1f5c597eb85f7447e5a6400b03e9fce10f8df168d68c`,
  igual ao `static/atlas-query-ui.js` atual.
- GitHub Actions consultado: último deploy web `40090652088`, commit
  `29197dd09317aab1659ec71e457e8056ffa1e14e`, success. Documentação posterior
  não representa novo deploy web. Os históricos `7e82da3` e `a3c96a7` foram
  lidos e tratam de evidências/documentação, não de novas correções operacionais.

## Dados preservados e verificação independente da autenticação Atlas

Backup SQLite consistente criado às 23:38:11:
`C:\DominiumRuntime\AtlasQueryData\backups\query_jobs.current-check-20261025-233811.sqlite3`.
38.989.824 bytes, `PRAGMA integrity_check=ok`, SHA-256
`e2c6cfabb3bc1ffa1612b9ed138ed658d8a2014b99ec0de6aa0ffd578c74c595`.

O serviço de exportação real foi executado numa cópia descartável desse backup,
com worker desativado. Os arquivos fonte privados foram reinterpretados e
comparados linha por linha com o banco. Nenhum dado de cliente foi impresso.

| Cidade | ID histórico | Linhas atuais persistidas | Fonte = banco | CSV = XLSX | HTTP CSV/XLSX |
| --- | --- | ---: | --- | --- | --- |
| Mossoró | 276855582 | 893 | sim | sim | 200/200 |
| Recife | 276861849 | 55.807 | sim | sim | 200/200 |
| Natal | 276868277 | 20.179 | sim | sim | 200/200 |
| Fortaleza | 276868465 / 276868467 | 0 | sem fonte | indisponível | não exportável |

ZIP dos três XLSX íntegro, sem fórmulas; 11 colunas. Isso valida os relatórios
salvos, **não** a geração atual dessas cidades. Downloads pelo Cloud Browser
das três cidades não foram repetidos nesta execução.

## Testes e limites

- 38 testes Python QUERY passaram após instalar websocket-client no ambiente
  de teste. A primeira execução falhou por dependência ausente, não por um
  defeito demonstrado da integração.
- 20 testes JavaScript QUERY passaram, incluindo sessão expirada, preservação
  do ID, timeout recuperável e prevenção de submissões duplicadas.
- Quality gate completo aprovado com `TZ=America/Sao_Paulo`: 900 testes Python
  executados, 21 ignorados, zero falhas; suites JavaScript, Ruff, build e auditoria
  do pacote aprovados (`QUALITY_GATE_OK`). O gate inicial encontrou índices
  já desatualizados e uma execução intermediária encontrou socksio ausente no
  ambiente de teste. Índices regenerados e dependência instalada localmente;
  nenhum arquivo de dependências ou runtime operacional foi alterado.
- Não se atribui a causa dos anexos 404 ao DOMINIUM, ao app-1 ou ao parser.
  Existe evidência histórica de falha na entrega BatAtlas e evidência atual
  de sessão expirada, que impede continuar a investigação da geração.

## Implementado, testado, publicado e ação necessária

- Implementado: diagnóstico sanitizado, backup e documentação. Nenhum patch
  operacional justificado pela evidência disponível; nenhum restart do Chrome.
- Testado: estado remoto, hashes, links existentes, interface Fortaleza,
  persistência após recarga, exportações salvas e testes automatizados acima.
- Publicação operacional: nenhuma nesta execução. Publicar apenas este
  checkpoint e a correção das instruções de continuidade no GitHub.
- Bloqueio que depende do operador: renovar login Atlas no Chrome gerenciado
  já aberto do DESKTOP-K7J3E1N, incluindo SSO/CAPTCHA se solicitado. Não enviar
  senha pelo chat. O login DOMINIUM já foi resolvido separadamente.
- Após login: verificar formulário e NetTask, criar uma nova QUERY controlada
  de Fortaleza pelo DOMINIUM, registrar ID, acompanhar anexo e validar o fluxo
  completo. Repetir geração atual nas outras três cidades. Não tratar relatórios
  históricos ready como comprovação de geração atual.
- Não foi criada tarefa de acompanhamento nesta execução. A atividade do
  worker do servidor é independente de qualquer tarefa do ChatGPT; nenhuma
  automação anterior foi verificada ou alterada aqui.
