"use strict";
const test=require("node:test");
const assert=require("node:assert/strict");
const image=require("../static/backlog-report-image.js");

const report={
  total:12,
  groups:[
    {label:"NATAL/RN",count:5,codeCounts:{"404":2,"430":2,"101":1}},
    {label:"FORTALEZA/CE",count:4,codeCounts:{"101":3,"306":1}},
    {label:"RECIFE/PE",count:1,codeCounts:{"306":1}},
    {label:"MOSSORÓ/RN",count:1,codeCounts:{"404":1}},
    {label:"PARNAMIRIM/RN",count:1,codeCounts:{"404":1}}
  ]
};
function fakeDocument(){
  const drawn=[];
  const canvas={width:0,height:0,getContext(){
    return {fillRect(){},strokeRect(){},beginPath(){},moveTo(){},lineTo(){},stroke(){},
      createLinearGradient(){return {addColorStop(){}};},
      fillText(value,x,y){drawn.push({value:String(value),x,y});}};
  }};
  return {drawn,canvas,doc:{createElement(tag){assert.equal(tag,"canvas");return canvas;}}};
}

test("PNG canvas always draws code quantities and city totals",()=>{
  const f=fakeDocument();
  image.createCanvas(report,f.doc);
  assert.equal(f.canvas.width,1600);
  assert.ok(f.canvas.height>=800);
  const values=f.drawn.map(x=>x.value);
  for(const city of report.groups)assert.ok(values.includes(city.label));
  assert.equal(values.filter(x=>x==="CÓDIGO").length,5);
  assert.equal(values.filter(x=>x==="QUANTIDADE").length,5);
  assert.equal(values.filter(x=>x==="TOTAL").length,5);
  assert.ok(values.includes("5"));
  assert.ok(values.includes("4"));
  assert.ok(values.includes("3"));
});
test("PNG adapts to single city or Natal/PWM without Fortaleza",()=>{
  const natal=image.imageDimensions(report.groups.slice(0,2));
  const one=image.imageDimensions(report.groups.slice(0,1));
  assert.equal(natal.cols,2);
  assert.equal(one.cols,1);
  assert.ok(one.width<natal.width);
  assert.ok(natal.width<image.imageDimensions(report.groups).width);
});
test("missing report rejects image export",()=>{
  assert.throws(()=>image.createCanvas({groups:[]},fakeDocument().doc),/não há códigos/i);
});
