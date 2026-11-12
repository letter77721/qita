const fs=require('node:fs');
const path=require('node:path');
const source=path.join(path.dirname(require.resolve('katex/package.json')),'dist','fonts');
const target=path.join(__dirname,'dist','_expo','static','css','fonts');
fs.mkdirSync(target,{recursive:true});
fs.cpSync(source,target,{recursive:true});
console.log('Copied math fonts for exported CSS');
