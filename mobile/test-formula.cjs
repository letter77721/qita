const assert=require('node:assert/strict');
const {formulaParts}=require('./formulaParts');
const katex=require('katex');
const fixtures=[
 '雷诺数： Re = '+String.raw`\frac{\rho v L}{\mu}`,
 String.raw`独立公式 $$Re=\frac{\rho v L}{\mu}$$`,
 String.raw`行内 \(Re=\frac{\rho v L}{\mu}\)`,
 '```latex\n'+String.raw`Re=\frac{\rho v L}{\mu}`+'\n```',
];
for(const fixture of fixtures){
 const math=formulaParts(fixture).filter(p=>p.math);
 assert.equal(math.length,1);
 assert.ok(katex.renderToString(math[0].value).includes('mfrac'));
}
assert.equal(formulaParts('普通文字雷诺数').some(p=>p.math),false);
console.log('Formula rendering regression checks passed');
