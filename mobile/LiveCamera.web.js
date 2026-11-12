import React, {forwardRef,useEffect,useRef,useState,useImperativeHandle} from 'react';

export default forwardRef(function LiveCamera({onCameraReady,onMountError},ref){
 const video=useRef(null),stream=useRef(null),generation=useRef(0);
 const [devices,setDevices]=useState([]),[selected,setSelected]=useState(''),[message,setMessage]=useState('正在请求后置相机…');
 const [manual,setManual]=useState(null),[distance,setDistance]=useState(0);
 async function focus(){
  const track=stream.current?.getVideoTracks()[0];const caps=track?.getCapabilities?.()||{};
  try{
   if(caps.focusMode?.includes('continuous')){await track.applyConstraints({advanced:[{focusMode:'continuous'}]});setMessage('已请求连续自动对焦，请保持约 20–40 厘米距离');}
   else if(caps.focusMode?.includes('single-shot')){await track.applyConstraints({advanced:[{focusMode:'single-shot'}]});setMessage('已请求重新对焦');}
   else setMessage('此浏览器未开放对焦控制。可切换镜头，或返回使用「系统相机拍摄」。');
  }catch{setMessage('浏览器未接受对焦设置，可尝试系统相机拍摄。');}
 }
 useImperativeHandle(ref,()=>({takePictureAsync:async()=>{
  const v=video.current;if(!v?.videoWidth)throw new Error('相机尚未就绪');
  const canvas=document.createElement('canvas');canvas.width=v.videoWidth;canvas.height=v.videoHeight;
  canvas.getContext('2d').drawImage(v,0,0);return {uri:canvas.toDataURL('image/jpeg',.98),width:canvas.width,height:canvas.height};
 }}),[]);
 useEffect(()=>{
  let active=true;const id=++generation.current;
  stream.current?.getTracks().forEach(t=>t.stop());
  (async()=>{
   try{
    const constraints=selected?{deviceId:{exact:selected},width:{ideal:1920},height:{ideal:1080}}:{facingMode:{ideal:'environment'},width:{ideal:1920},height:{ideal:1080}};
    let media;try{media=await navigator.mediaDevices.getUserMedia({video:constraints,audio:false});}catch(e){if(selected)throw e;media=await navigator.mediaDevices.getUserMedia({video:{facingMode:{ideal:'environment'}},audio:false});}
    if(!active||id!==generation.current){media.getTracks().forEach(t=>t.stop());return;}
    stream.current=media;video.current.srcObject=media;await video.current.play();
    const cameras=(await navigator.mediaDevices.enumerateDevices()).filter(d=>d.kind==='videoinput');if(active)setDevices(cameras);
    const track=media.getVideoTracks()[0],caps=track.getCapabilities?.()||{};
    if(active)setManual(caps.focusMode?.includes('manual')&&caps.focusDistance?caps.focusDistance:null);
    await focus();if(active)onCameraReady?.();
   }catch(e){if(active){setMessage(e.message);onMountError?.(e);}}
  })();
  return()=>{active=false;stream.current?.getTracks().forEach(t=>t.stop());};
 },[selected]);
 return <div style={{flex:1,minHeight:220,display:'flex',flexDirection:'column',background:'#102822',color:'white'}}>
  <video ref={video} autoPlay muted playsInline onClick={focus} style={{width:'100%',minHeight:180,flex:1,objectFit:'contain',maxHeight:'58vh'}}/>
  <div style={{padding:12,fontSize:13,lineHeight:1.6}}>{message}</div>
  <div style={{display:'flex',gap:8,padding:12,flexWrap:'wrap'}}><button type="button" onClick={focus}>重新对焦</button>
   {devices.length>1&&<select aria-label="选择相机镜头" value={selected} onChange={e=>setSelected(e.target.value)}><option value="">默认后置镜头</option>{devices.map((d,i)=><option key={d.deviceId} value={d.deviceId}>{d.label||`镜头 ${i+1}`}</option>)}</select>}
   {manual&&<label>手动焦距<input aria-label="手动焦距" type="range" min={manual.min} max={manual.max} step={manual.step||.01} value={distance} onChange={async e=>{const value=Number(e.target.value);setDistance(value);try{await stream.current.getVideoTracks()[0].applyConstraints({advanced:[{focusMode:'manual',focusDistance:value}]});}catch{setMessage('该设备未接受手动焦距设置');}}}/></label>}
  </div>
 </div>;
});
