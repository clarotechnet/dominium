# DOMINIUM — Central de Controladores TOA (homologação)

Atualização: 07/11/2026.

## Escopo

Local: **Central inteligente → Central de Controladores**. Tela de administração e observabilidade das pontes TOA dos controladores. Não confundir com Controle de baixas (fila operacional por O.S.) nem com Análise Backlog (base da Claro x Imperium).

Informações: controlador identificado, online/offline, ocupado/livre, última atividade, contador de consultas reportadas, buckets verificados, cobertura por bucket, filas aguardando, inscrições pendentes e simulação de distribuição. Cada bucket corresponde ao catálogo oficial fornecido pelo operador em 07/11/2026.

## Segurança e integração

- `GET /api/toa-pool/monitor`: exige usuário administrador autenticado no DOMINIUM; busca `/admin/status` do coordenador com token lido exclusivamente de variável de ambiente e elimina campos sensíveis antes de responder.
- `GET /api/toa-pool/enrollments`: lista apenas IDs de inscrições pendentes.
- `POST /api/toa-pool/enrollments/<id>/approve|deny`: exige administrador e CSRF válido. Ações devem comparar o código no popup da extensão antes da confirmação.
- Variáveis **somente no servidor**, nunca no HTML/JS: `DOMINIUM_TOA_POOL_ORIGIN` (HTTP loopback ou HTTPS) e `DOMINIUM_TOA_POOL_ADMIN_TOKEN`. Nenhuma delas foi configurada em produção nesta etapa.
- O coordenador não está publicado como endpoint HTTPS próprio; a extensão plug-and-play v2.7.0 tem origem pública em branco. Não distribuir como operacional.
- Ausência de configuração resulta em 503 com mensagem genérica. Não realiza nenhuma consulta Oracle ou baixa de O.S.
- Não iniciar serviço TOA 8792, não modificar BOT DMV nem Bridge Atlas/TOA existente.
- Backups dos arquivos modificados: `backups/controller-central-20261107` (não versionados).
- O código está em branch de homologação. Não houve deploy na Hostinger.

## Simulação de alocação

A tela simula distribuição de 50 contratos por 10 controladores elegíveis e livres como 5 propostas por controlador. Não é comando de execução. Sessões ocupadas, offline ou sem o bucket correto não são elegíveis. A execução real exige prioridade por janela de atendimento, deduplicação, cooldown, identidade de O.S. e orçamento global autorizado.

## Catálogo de buckets

- Fortaleza: `FTZ-DMV_01` (Adesão), `FTZ-DMV_ADM` (DESC), `FTZ-DMV_01_VT` (VT).
- Recife: `JCR-DMV` (Adesão), `JCR-DMV_ADM` (DESC).
- Mossoró: `MRO-DMV` (Adesão/DESC/VT).
- Natal: `NTL-DMV` (Adesão), `NTL-DMV_ADM` (DESC), `NTL-DMV_VT` (VT).
- Parnamirim: `PWM-DMV` (Adesão), `PWM-DMV_ADM` (DESC), `PWM-DMV_VT` (VT).

`JCR-DMV_VT` não foi fornecido como bucket operacional e não é inventado pelo catálogo.

## Testes

- Node: teste determinístico do catálogo, sessão offline, distribuição 50/10, privacidade e endpoint same-origin.
- Python: proxy admin e CSRF, origem segura, sanear resposta e proibir vazamento de token/contrato.
- Browser headless: painel renderizado com dados fictícios e inscrição de demonstração sem ação de aprovação.
- Testes de regressão Controle de baixas e Análise Backlog executados separadamente.

## Próximos passos

1. Publicar e validar endpoint do coordenador por HTTPS, preservando o token admin somente no servidor e evitando expor o serviço de administração ao público.
2. Configurar variáveis de ambiente em backend autorizado e validar monitor autenticado com sessão real.
3. Confirmar limite global de requisições Oracle com a Claro; o limite de leases não é contador HTTP.
4. Homologar um controlador e autorização central; verificar identificador e 12 buckets.
5. Só depois avaliar distribuição automática, monitoramento e deploy gradual.
