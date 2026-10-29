'use strict';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const pilot = require('../integrations/desc_runtime/bot/disconnectPilot');
const parse = (text, chatId=pilot.NATAL_CHAT_ID) => pilot.parseDisconnectMessage({
  text, chatId, messageId:'message-test', senderId:'sender-test',
  receivedAt:'2026-10-29T18:00:00Z',
});

test('contratos de Recife com nove dígitos seguem para consulta TOA',()=>{
  for (const text of ['900000001 ret 1 mta 1 fonte',
                      '900000001 cod.430 coletado 1 decoder',
                      'CONTRATO: 900000001\nMotivo 430']) {
    const event = parse(text, pilot.RECIFE_CHAT_ID);
    assert.equal(event.contract,'900000001');
    assert.equal(event.profile_key,'recife');
  }
});
test('contrato sozinho e relatos não inventam código de baixa',()=>{
  for (const text of ['4000001', '4000001 fr', '4000001 retirado 1 EMTA e 1 fonte']) {
    assert.equal(parse(text).requested_close_code, null);
    assert.equal(parse(text).contract, '4000001');
  }
});
test('código explícito nos formatos reais é conservado como evidência',()=>{
  for (const text of ['4000001-106 cliente ausente','4000001\n430\nFora Rota',
                      'CONTRATO: 4000001\nMotivo 430', '4000001 cod.430 coletado']) {
    const e = parse(text);
    assert.equal(e.contract,'4000001');
    assert.equal(e.requested_close_code || e.unsupported_close_code,
                 text.includes('106') ? '106' : '430');
  }
});
test('endereço e agenda não viram código nem impedem consulta do contrato',()=>{
  const e=parse('CONTRATO: 4000001\nEND: AV TESTE, 425, AP 902\nAGENDA: 11:00 - 14:00\nMotivo 430');
  assert.equal(e.contract,'4000001');
  assert.equal(e.requested_close_code,'430');
});
test('vários contratos ou códigos conflitantes bloqueiam',()=>{
  assert.throws(()=>parse('4000001 e 4000002 430'), /multiple_contracts/);
  assert.throws(()=>parse('4000001 430 cod 409'), /message_format_invalid/);
  assert.throws(()=>parse('3902235430 e 4000001430'), /multiple_contracts/);
  assert.throws(()=>parse('3902235430 e 4000001'), /multiple_contracts/);
  assert.throws(()=>parse('4303902430'), /multiple_contracts/);
});
test('contrato e código compactos não perdem a identidade',()=>{
  for (const text of ['4000001430','4304000001']) {
    const event=parse(text);
    assert.equal(event.contract,'4000001');
    assert.equal(event.requested_close_code,'430');
  }
});
test('telefone e serial isolados não viram contrato',()=>{
  for (const text of ['5584999999999', '241786079210', '1199999999']) {
    assert.throws(()=>parse(text),/missing_contract/);
  }
});
test('grupo desconhecido e comando não entram no fluxo DESC',()=>{
  assert.throws(()=>parse('4000001 430','unknown@g.us'), /unknown_whatsapp_group/);
  assert.throws(()=>parse('!atlas 4000001'), /command_not_contract_message/);
});
test('mensagem repetindo o mesmo contrato mantém identidade única',()=>{
  assert.equal(parse('CONTRATO: 4000001\n4000001 430').contract,'4000001');
});
