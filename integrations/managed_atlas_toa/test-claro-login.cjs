'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const code=fs.readFileSync(__dirname+'/claro-login-submit.js','utf8');
function simulate({host='cap.claro.com.br',path='/loginapp2fa/',username='EXEMPLO',password='SENHA_FICTICIA',captcha=false,recent=false}={}){
  const events=[];
  let clicks=0, stopped=0;
  const vault=new Map();
  if(recent)vault.set('dominium.claro-login.last-submit',String(Date.now()));
  class Input {
    constructor(id,val){this.id=id;this._value=val;this.disabled=false;}
    get value(){return this._value;}
    set value(v){this._value=v;events.push([this.id,v.length]);}
    dispatchEvent(){return true;}
  }
  const user=new Input('user',username),pass=new Input('pass',password);
  const button={tagName:'BUTTON',textContent:'ENVIAR',disabled:false,click(){clicks++;}};
  const form={
    querySelector(sel){return sel.includes('name="username"')?user:sel.includes('name="password"')?pass:null;},
    querySelectorAll(){return [button];}
  };
  const ctx={
    location:{hostname:host,pathname:path},
    document:{querySelector(){return captcha?{}:null;},querySelectorAll(){return [form];}},
    HTMLInputElement:Input,Event:class{},
    sessionStorage:{getItem(k){return vault.get(k)},setItem(k,v){vault.set(k,v)}},
    setInterval(){return 1;},clearInterval(){stopped++;},
    Date,
  };
  vm.runInNewContext(code,ctx,{timeout:300});
  return {events,clicks,user:user.value,pass:pass.value,stopped,attempted:vault.has('dominium.claro-login.last-submit')};
}
let result=simulate();
assert.equal(result.clicks,1,'click only once');
assert.equal(result.user,'EXEMPLO');assert.equal(result.pass,'SENHA_FICTICIA');
assert.deepEqual(result.events,[['user',0],['user',7],['pass',0],['pass',14]]);
assert.equal(result.attempted,true);
assert.equal(simulate({password:''}).clicks,0);
assert.equal(simulate({captcha:true}).clicks,0);
assert.equal(simulate({host:'example.org'}).clicks,0);
assert.equal(simulate({recent:true}).clicks,0);
console.log('OK 5 scenarios: filled, blank, challenge, wrong host, retry guard');