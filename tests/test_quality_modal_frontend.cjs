'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const ROOT = path.join(__dirname, '..');

class FakeElement {
  constructor(id='') {
    this.id=id;
    this.attrs={};
    this.events={};
    this.hidden=false;
    this.disabled=false;
    this.open=false;
    this.value='';
    this.textContent='';
    this.children=[];
    this.isConnected=true;
    const classes=new Set();
    this.classList={
      toggle(name, force) {
        if(force===undefined) force=!classes.has(name);
        if(force) classes.add(name); else classes.delete(name);
      },
      contains(name) {return classes.has(name);}
    };
  }
  addEventListener(name,fn) {(this.events[name] ||= []).push(fn);}
  dispatchEvent(event) {for(const handler of this.events[event.type]||[])handler(event);}
  click() {this.dispatchEvent({type:'click',preventDefault(){}});}
  focus() {this.focused=true;}
  showModal() {this.open=true;}
  close() {this.open=false;this.dispatchEvent({type:'close'});}
  reset() {for (const input of this.inputs||[]) input.value='';}
  appendChild(node) {this.children.push(node);}
  replaceChildren(...nodes) {this.children=nodes.flatMap(n=>n.isFragment?n.children:[n]);}
  setAttribute(name,value) {this.attrs[name]=String(value);}
  getAttribute(name) {return this.attrs[name]||null;}
}

function makeDOM() {
 const ids=['stockInventoryTab','stockQualityTab','stockInventoryPane','stockQualityPane','qualityBody',
  'qualityFormWrap','qualityForm','qualityNotice','qualityFormNotice','qualityFormTitle','qualitySearch',
  'qualityCount','qualityAdd','qualitySave','qualityCancel','qualityDialogClose','qualityRefresh',
  'qualityMaterial','qualityDescription','qualityRule','stockGroupToggle','stockNavChildren',
  'stockModule','serialsModule','stockQualityModule'];
 const nodes=Object.fromEntries(ids.map(id=>[id,new FakeElement(id)]));
 nodes.qualityForm.inputs=[nodes.qualityMaterial,nodes.qualityDescription,nodes.qualityRule];
 const docListeners={};
 const document={
   activeElement:nodes.qualityAdd,
   getElementById(id){return nodes[id]||null;},
   createElement(){return new FakeElement();},
   createDocumentFragment(){const v=new FakeElement();v.isFragment=true;return v;},
   addEventListener(type,fn){(docListeners[type] ||= []).push(fn);},
   dispatchEvent(event){for(const fn of docListeners[event.type]||[])fn(event);}
 };
 return {nodes,document};
}

const tick=()=>new Promise(resolve=>setImmediate(resolve));

function startUI(role='admin') {
 const {nodes,document}=makeDOM();
 const api=[];
 const state={authUser:{role},activeModule:'stock'};
 let failWrites=false;
 const request=async (url,opts)=>{
   api.push({url,opts});
   if(opts?.method==='POST'){
     if(failWrites) throw Error('Falha temporaria de gravacao');
     return {ok:true,item:{id:7}};
   }
   return {items:[{id:7,material:'22026210',descricao_material:'Cabo HDMI',qtd_controle_qualidade:'2',atualizado_em:'2026-10-27T13:18:24+00:00'}]};
 };
 const context={document,state,request,normalize:x=>x.toLowerCase(),showToast:()=>{},window:{},
   console,Date,Promise,setTimeout,clearTimeout};
 vm.runInNewContext(fs.readFileSync(path.join(ROOT,'static/quality-control.js'),'utf8'),context);
 return {nodes,state,api,setFail:v=>{failWrites=v;}};
}

test('quality control add/edit opens modal rather than inline form',async()=>{
 const {nodes,api}=startUI();
 assert.equal(nodes.qualityFormWrap.open,false);
 nodes.stockQualityTab.click();
 await tick();
 assert.equal(nodes.qualityCount.textContent,'1 de 1 materiais');
 nodes.qualityAdd.click();
 assert.equal(nodes.qualityFormWrap.open,true);
 assert.equal(nodes.qualityFormTitle.textContent,'Adicionar material');
 assert.equal(nodes.qualityMaterial.value,'');
 nodes.qualityCancel.click();
 assert.equal(nodes.qualityFormWrap.open,false);
 const row=nodes.qualityBody.children[0];
 assert.equal(row.children[0].textContent,'22026210');
 const edit=row.children[4].children[0];
 edit.click();
 assert.equal(nodes.qualityFormWrap.open,true);
 assert.equal(nodes.qualityFormTitle.textContent,'Editar material');
 assert.equal(nodes.qualityMaterial.value,'22026210');
 assert.equal(nodes.qualityRule.value,'2');
 nodes.qualityRule.value='menor que 4';
 nodes.qualityForm.dispatchEvent({type:'submit',preventDefault(){}});
 await tick();await tick();
 const post=api.find(item=>item.opts?.method==='POST');
 assert.equal(JSON.parse(post.opts.body).id,7);
 assert.equal(JSON.parse(post.opts.body).qtd_controle_qualidade,'menor que 4');
 assert.equal(nodes.qualityFormWrap.open,false);
});

test('failed save leaves modal open and preserves entered data',async()=>{
 const {nodes,setFail}=startUI();
 nodes.stockQualityTab.click();
 await tick();
 setFail(true);
 nodes.qualityAdd.click();
 nodes.qualityMaterial.value='8899';
 nodes.qualityDescription.value='Material teste';
 nodes.qualityRule.value='variável';
 nodes.qualityForm.dispatchEvent({type:'submit',preventDefault(){}});
 await tick();
 assert.equal(nodes.qualityFormWrap.open,true);
 assert.equal(nodes.qualityRule.value,'variável');
 assert.match(nodes.qualityFormNotice.textContent,/temporaria/i);
 assert.equal(nodes.qualitySave.disabled,false);
 nodes.qualityDialogClose.click();
 assert.equal(nodes.qualityFormWrap.open,false);
});

test('viewer cannot open add form nor edit records',async()=>{
 const {nodes}=startUI('viewer');
 nodes.stockQualityTab.click();
 await tick();
 assert.equal(nodes.qualityAdd.hidden,true);
 nodes.qualityAdd.click();
 assert.equal(nodes.qualityFormWrap.open,false);
 assert.equal(nodes.qualityBody.children[0].children[4].textContent,'Somente leitura');
});

test('Estoque chevron and children switch state on every click',()=>{
 const {nodes,document}=makeDOM();
 nodes.stockGroupToggle.setAttribute('aria-expanded','true');
 nodes.stockQualityTab.setAttribute('aria-selected','false');
 const state={activeModule:'stock'};
 const winListeners={};
 const window={
   location:{hash:'#estoque',href:'https://dominium.clarotechnet.com.br/?profile=natal#estoque',pathname:'/',search:'?profile=natal'},
   history:{replaceState(){}},
   addEventListener(type,fn){(winListeners[type] ||= []).push(fn);}
 };
 vm.runInNewContext(fs.readFileSync(path.join(ROOT,'static/stock-nav.js'),'utf8'),{
   document,state,window,URL
 });
 nodes.stockGroupToggle.click();
 assert.equal(nodes.stockGroupToggle.getAttribute('aria-expanded'),'false');
 assert.equal(nodes.stockNavChildren.hidden,true);
 nodes.stockGroupToggle.click();
 assert.equal(nodes.stockGroupToggle.getAttribute('aria-expanded'),'true');
 assert.equal(nodes.stockNavChildren.hidden,false);
 nodes.stockGroupToggle.click();
 state.activeModule='serials';
 document.dispatchEvent({type:'dominium:module-change'});
 assert.equal(nodes.stockGroupToggle.getAttribute('aria-expanded'),'true');
});
