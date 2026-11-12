import React from 'react';
import katex from 'katex';
import 'katex/dist/katex.min.css';
import {formulaParts} from './formulaParts';

export default function MathText({text=''}){
 return <div style={{fontSize:15,lineHeight:1.85,color:'#172F3C',whiteSpace:'pre-wrap',overflowX:'auto',marginTop:10}}>{formulaParts(text).map(({math,display,value:source},i)=>{
  if(!math)return <React.Fragment key={i}>{source}</React.Fragment>;
  try{return <span key={i} aria-label={source} dangerouslySetInnerHTML={{__html:katex.renderToString(source,{displayMode:display,throwOnError:false,trust:false,maxExpand:500,strict:'warn'})}}/>;}
  catch{return <span key={i}>{source}</span>;}
 })}</div>;
}
