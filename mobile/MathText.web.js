import React from 'react';
import katex from 'katex';
import 'katex/dist/katex.min.css';

export default function MathText({text=''}){
 const normalized=String(text).replace(/```(?:latex|math)\s*([\s\S]*?)```/g,(_,formula)=>'$$'+formula.trim()+'$$');
 const parts=normalized.split(/(\$\$[\s\S]*?\$\$|\$[^$\n]+\$|\\\[[\s\S]*?\\\]|\\\([^\n]*?\\\))/g);
 return <div style={{fontSize:15,lineHeight:1.85,color:'#172F3C',whiteSpace:'pre-wrap',overflowX:'auto',marginTop:10}}>{parts.map((part,i)=>{
  const display=part.startsWith('$$')||part.startsWith('\\[');
  const math=display||part.startsWith('$')||part.startsWith('\\(');
  if(!math)return <React.Fragment key={i}>{part}</React.Fragment>;
  const source=part.slice(display||part.startsWith('\\(')?2:1,display||part.startsWith('\\(')?-2:-1);
  try{return <span key={i} aria-label={source} dangerouslySetInnerHTML={{__html:katex.renderToString(source,{displayMode:display,throwOnError:false,trust:false,maxExpand:500,strict:'warn'})}}/>;}
  catch{return <span key={i}>{part}</span>;}
 })}</div>;
}
