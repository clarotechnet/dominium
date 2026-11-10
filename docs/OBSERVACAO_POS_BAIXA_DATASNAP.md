# DOMINIUM — observação pós-baixa via DataSnap

**Escopo:** piloto Natal/Parnamirim (perfil `natal`). Escrita restrita ao administrador, desabilitada por padrão.

## Estado de implantacao local (10/11/2026)

Servidor TECHNET: painel HTTP 8791 validado com HTML, JS e CSS contendo o recurso. A instancia local tem a flag de escrita habilitada para o piloto Natal. A versao GitHub/Hostinger tem ciclo de publicacao independente; nenhuma nova escrita real foi feita durante esta integracao.

## Situação homologada

Em 10/11/2026, uma única atualização de `ObservacaoBaixa` foi executada na O.S. 2664945723, contrato 4332297 (já concluída com 409), mediante autorização do operador. Houve confirmação de leitura independente do texto acrescentado, preservação do conteúdo anterior, código 409 e restante do registro DataSnap.

**Não há homologação de escrita de observação para outras cidades.**

## Fluxo

1. O administrador abre **Base operacional → Ordens e tarefas → Adicionar observação** ou usa **Observação em O.S. concluída** com data, contrato e número da O.S. Essa segunda opção consulta diretamente o DataSnap, mesmo sem histórico local.
2. Preenche apenas o texto complementar (máximo 500 caracteres, uma linha).
3. O painel executa `POST /api/orders/{id_os}/observation/preview?profile=natal`.
4. O backend verifica contrato, número de O.S., código 409 e registro atual, montando a prévia sem enviar escrita.
5. Após confirmação explícita do usuário, `POST /api/orders/{id_os}/observation/append?profile=natal` envia um único `AS_ApplyUpdates` limitado ao campo `ObservacaoBaixa`.
6. A operação usa hash do snapshot, UUID idempotente e bloqueio exclusivo por O.S. O servidor confirma por uma nova leitura e compara todos os campos, exceto a observação.
7. Resposta incerta **não autoriza reenvio**. Consultar O.S. e auditoria antes de qualquer nova operação.

## Segurança e ativação

- `DOMINIUM_ENABLE_POST_CLOSE_OBSERVATIONS=1` habilita escrita somente no processo web do DOMINIUM, exclusivamente para administradores e perfil Natal.
- A variável deve estar ausente ou diferente de `1` até concluir a validação de implantação.
- Sessão DOMINIUM, CSRF, origem, rate limiting e `OPERATION_GATE` são os existentes no painel.
- O texto da observação não é incluído no arquivo de auditoria, que registra apenas hashes, comprimentos e resultado.
- O módulo não acessa endpoints de baixa, equipamento ou estoque.
- Status/código/identidade são conferidos antes da escrita.
- Nunca reutilizar pacotes brutos ou credenciais capturados.

## Artefatos locais

- `obs_datasnap_lab.py`: decoder e construtor DataSnap da observação.
- `obs_datasnap_operation_lab.py`: prévia, locks, auditoria e gravação de envio único.
- `tests/test_obs_datasnap_lab.py`: casos sintéticos do formato.
- `tests/test_obs_datasnap_operation_lab.py`: simulação de concorrência, confirmação e timeout.
- `tests/test_post_close_observation_routes.py`: autenticação e integração HTTP simulada.
- `tests/test_post_close_observation_lookup.py`: consulta direta segura por data, contrato e número da O.S.

## Rollback

Backup pré-alteração no servidor: `F:\Dominium\Backups\POST_CLOSE_OBS_INTEGRACAO_20261110_PRE`.

Primeiro, desligar `DOMINIUM_ENABLE_POST_CLOSE_OBSERVATIONS` no processo web. Caso necessário, restaurar os arquivos `app.py`, `static/app.js`, `static/index.html` e `static/styles.css` a partir do backup, reiniciar o painel sob o mesmo supervisor e verificar as rotas de sessão e a baixa. Nunca apagar o log de idempotência para tentar novamente um envio incerto.

## Limitações

- Se a **Base operacional** não possuir o IdOS, use a consulta direta de O.S. concluída por data, contrato e número. O resolvedor está limitado aos últimos 90 dias em Natal.
- Apenas observações de O.S. 409 estão implementadas nesta versão. Outros códigos exigem homologação de máscara/estado.
- A escrita pelo processo web só funcionará onde houver acesso autenticado ao DataSnap; o frontend hospedado fora da rede não substitui esse acesso.
