// Preserve ordinary prose; normalize bare LaTeX from model responses for display only.
function formulaParts(text='') {
 const normalized=String(text).replace(/```(?:latex|math)\s*([\s\S]*?)```/g,(_,f)=>'$$'+f.trim()+'$$');
 const parts=normalized.split(/(\$\$[\s\S]*?\$\$|\$[^$\n]+\$|\\\[[\s\S]*?\\\]|\\\([^\n]*?\\\))/g);
 return parts.flatMap(part=>{
  const display=part.startsWith('$$')||part.startsWith('\\[');
  const math=display||part.startsWith('$')||part.startsWith('\\(');
  if(math)return [{math:true,display,value:part.slice(display||part.startsWith('\\(')?2:1,display||part.startsWith('\\(')?-2:-1)}];
  return part.split(/(\n)/).flatMap(line=>{
   if(!/\\(?:frac|dfrac|sqrt|rho|mu|nu|tau|alpha|beta|lambda|Delta|int|sum|partial|cdot|times)\b/.test(line))return [{math:false,value:line}];
   const equation=line.search(/\\?[A-Za-z\u0370-\u03ff][A-Za-z0-9_{}\\^\u0370-\u03ff]*\s*=/);
   const start=equation>=0?equation:line.indexOf('\\');
   return [{math:false,value:line.slice(0,start)},{math:true,display:false,value:line.slice(start).trim()}];
  });
 });
}
module.exports={formulaParts};
