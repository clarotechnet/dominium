# Credencial compartilhada dos relatórios — 17/11/2026

Os downloads de OS (bruto e tratado) e de Comissão retornavam HTTP 502. A consulta
direta reproduziu OSError do Windows na descriptografia DPAPI da credencial
legada de DominiumMain. A conexão TCP nas quatro bases estava disponível e a
credencial do runtime Imperium ativo autenticou corretamente a conta operacional.

Correção: order_reports.CREDENTIALS acompanha a mesma raiz de RUNTIME, incluindo
DOMINIUM_IMPERIUM_RUNTIME_ROOT quando configurada. commission_reports importa
esse padrão compartilhado. Nenhuma senha foi exibida, copiada ou regravada.
Patch cirúrgico no runtime complementar com backup; demais rotas preservadas.

Teste novo em processo isolado comprovou a falha antes da correção e passou
depois. Verifica que os dois clientes selecionam a credencial protegida do
runtime ativo mesmo havendo uma credencial legada; impede conexão de rede real
no teste. Dezessete testes focados de credenciais, OS e comissões aprovados.

Verificação pela ponte publicada:
- Comissão nas quatro cidades, de 01 a 16/11: HTTP 200 e XLSX válido.
- OS Mossoró de 16/11, bruto e tratado: HTTP 200 e XLSX válido.
- Manutenção tratada de Mossoró: HTTP 200 e XLSX válido.
- Automação TOA e snapshot operacional: HTTP 200.

O 502 de TOA não foi reproduzido na verificação atual; havia erro anterior de
conexão recusada ao backend no conector. Não atribuir esse evento à credencial
dos relatórios. Não houve reenvio de baixa, alteração de materiais ou mudanças
nos executores operacionais.
