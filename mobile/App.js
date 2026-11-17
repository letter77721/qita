import React,{useState,useEffect,useMemo,useRef} from 'react';
import {View,Text,Pressable,ScrollView,TextInput,StyleSheet,Modal,ActivityIndicator,Platform,Image,Linking} from 'react-native';
import {SafeAreaProvider,SafeAreaView} from 'react-native-safe-area-context';
import {Ionicons} from '@expo/vector-icons';
import * as DocumentPicker from 'expo-document-picker';
import MathText from './MathText';

const tabs=[['首页','home-outline'],['AI练习','sparkles-outline'],['错题本','book-outline'],['我的','person-outline']];
const goalOptions=['理解基本概念','掌握公式与适用条件','训练解题方法','考前巩固复习'];
const VERDICT={correct:'正确',incorrect:'错误',uncertain:'待定'};
const ERRORTYPE={concept:'概念理解',condition:'适用条件',calculation:'计算过程',memory:'知识记忆',none:'请查看解析'};

function Btn({title,onPress,disabled=false,variant='soft',icon}){
 return <Pressable accessibilityRole="button" accessibilityLabel={title} onPress={onPress} disabled={disabled}
  style={[s.btn,variant==='primary'?s.btnPrimary:variant==='ghost'?s.btnGhost:s.btnSoft,disabled&&{opacity:.45}]}>
  {icon?<Ionicons name={icon} size={16} color={variant==='primary'?'#FFFFFF':'#2E6BE6'}/>:null}
  <Text style={[s.bt,variant==='primary'?{color:'#FFFFFF'}:variant==='ghost'?{color:'#6B7280'}:null]}>{title}</Text>
 </Pressable>
}
function Card({children,style}){return <View style={[s.card,style]}>{children}</View>}
function Input({value,onChangeText,placeholder,multiline=false,secureTextEntry=false}){return <TextInput accessibilityLabel={placeholder} {...{value,onChangeText,placeholder,multiline,secureTextEntry}} autoCapitalize="none" style={[s.input,multiline&&{minHeight:110,textAlignVertical:'top'}]}/>}
function SectionHead({index,title,desc}){
 return <View style={s.secHead}>
  {index?<View style={s.secNum}><Text style={s.secNumText}>{index}</Text></View>:null}
  <View style={{flex:1}}><Text style={s.secTitle}>{title}</Text>{desc?<Text style={s.secDesc}>{desc}</Text>:null}</View>
 </View>
}
function Pill({text,tone='soft'}){
 return <View style={[s.pill,tone==='warn'?s.pillWarn:tone==='ok'?s.pillOk:tone==='blue'?s.pillBlue:s.pillSoft]}>
  <Text style={[s.pillText,tone==='warn'?{color:'#9A4A1E'}:tone==='ok'?{color:'#1F7A5A'}:tone==='blue'?{color:'#2E6BE6'}:null]}>{text}</Text>
 </View>
}
function Stat({label,value,accent}){
 return <View style={s.stat}>
  <Text style={[s.statValue,accent&&{color:'#2E6BE6'}]}>{value}</Text>
  <Text style={s.statLabel}>{label}</Text>
 </View>
}
function Bar({ratio}){
 const pct=Math.max(0,Math.min(1,ratio||0));
 return <View style={s.bar}><View style={[s.barFill,{width:(pct*100)+'%'}]}/></View>
}
function dueLabel(due){
 if(!due)return '未安排';
 const today=new Date().toLocaleDateString('en-CA',{timeZone:'Asia/Shanghai'});
 if(due<today)return '已到期 · '+due;
 if(due===today)return '今天复习';
 return due+' 复习';
}

export default function App(){return <SafeAreaProvider><Lite/></SafeAreaProvider>}

function Lite(){
 const [tab,setTab]=useState('首页'),[host,setHost]=useState(Platform.OS==='web'?window.location.origin:'https://notepilot-w8tp.onrender.com');
 const [data,setData]=useState(null),[overview,setOverview]=useState(null),[course,setCourse]=useState('fluid'),[busy,setBusy]=useState(false),[error,setError]=useState(''),[note,setNote]=useState(''),[modal,setModal]=useState('');
 const [manageCourse,setManageCourse]=useState(null),[rename,setRename]=useState('');
 const [goalTarget,setGoalTarget]=useState(goalOptions[0]),[documentId,setDocumentId]=useState('');
 const [concept,setConcept]=useState(''),[target,setTarget]=useState(''),[source,setSource]=useState(''),[question,setQuestion]=useState(null),[answer,setAnswer]=useState(''),[feedback,setFeedback]=useState(null),[hint,setHint]=useState(false),[editId,setEditId]=useState(''),[courseName,setCourseName]=useState(''),[page,setPage]=useState(null),[pageEdit,setPageEdit]=useState('');
 const [openGoal,setOpenGoal]=useState('');

 async function api(path,body,method){const r=await fetch(host.replace(/\/$/,'')+'/api/open'+path,{method:method||(body?'POST':'GET'),credentials:'include',cache:'no-store',headers:{...(body instanceof FormData?{}:{'Content-Type':'application/json'})},...(body?{body:body instanceof FormData?body:JSON.stringify(body)}:{})});let d;try{d=await r.json()}catch{throw Error('服务器响应无效')}if(!r.ok)throw Error(typeof d.detail==='string'?d.detail:'输入或请求无效');return d}
 async function act(fn){setBusy(true);setError('');try{await fn()}catch(e){setError(e.message)}finally{setBusy(false)}}
 async function refresh(){
  const courses=await api('/courses');
  if(!courses.some(c=>c.id===course)){setCourse(courses[0].id);return}
  const [dash,over]=await Promise.all([api('/lite/dashboard?course_id='+course),api('/lite/overview')]);
  setData(dash);setOverview(over);
 }
 useEffect(()=>{setData(null);setQuestion(null);setFeedback(null);setOpenGoal('');act(refresh)},[course,host]);
 function clear(){setGoalTarget(goalOptions[0]);setDocumentId('');setConcept('');setTarget('');setSource('');setAnswer('');setEditId('')}
 function requireLogin(fn){act(fn)}
 async function start(goal){const q=await api('/lite/questions',{goal_id:goal,course_id:course});setQuestion(q);setAnswer('');setFeedback(null);setHint(false);setTab('AI练习')}
 async function documents(){const picked=await DocumentPicker.getDocumentAsync({type:['application/pdf','text/plain','text/markdown'],copyToCacheDirectory:true});if(picked.canceled)return;const a=picked.assets[0],f=new FormData();if(Platform.OS==='web')f.append('file',a.file||await(await fetch(a.uri)).blob(),a.name);else f.append('file',{uri:a.uri,name:a.name,type:a.mimeType});f.append('course_id',course);f.append('kind','课程课件');const u=await api('/documents',f);await refresh();setNote('资料已上传，等待文字提取…');for(let n=0;n<60;n++){await new Promise(r=>setTimeout(r,1000));const j=await api('/documents/'+u.document_id+'/status');if(j?.status==='failed'){await refresh();setNote('');throw Error(j.error||'文件解析失败，请换用文字版 PDF / TXT / MD')}if(j?.status==='completed'){setNote('资料处理完成。文字版 PDF / TXT / MD 可自动作为学习依据；纯扫描件暂不支持。');await refresh();return u.document_id}}setNote('仍在处理，稍后点击刷新资料。')}

 const tasks=data?.tasks||[];
 const current=overview?.courses?.find(c=>c.id===course);
 const goalsById=useMemo(()=>{const m={};(data?.history||[]).forEach(h=>{const item={...h,error_type:h.evaluation?.error_type};(m[h.goal_id]=m[h.goal_id]||[]).push(item)});return m},[data]);
 const dueCount=current?current.due_today:0;
 const today=useMemo(()=>new Date().toLocaleDateString('en-CA',{timeZone:'Asia/Shanghai'}),[]);
 const otherCourses=useMemo(()=>(data?.courses||[]).filter(c=>c.id!==manageCourse?.id),[data,manageCourse]);
 const masteredCount=useMemo(()=>tasks.filter(g=>g.level==='近期较稳定，继续验证').length,[tasks]);
 const progressPct=tasks.length?Math.round(masteredCount/tasks.length*100):0;

 function CoursePicker(){
  const list=overview?.courses||[];
  if(!list.length)return null;
  return <View style={s.pickerWrap}>
   <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={s.pickerRow}>
    {list.map(c=>{
     const on=c.id===course;
     return <Pressable key={c.id} accessibilityRole="button" accessibilityLabel={'课程 '+c.name} accessibilityState={{selected:on}}
      disabled={busy} onPress={()=>setCourse(c.id)} style={[s.pickCard,on&&s.pickCardOn]}>
      <Text style={[s.pickName,on&&{color:'#FFFFFF'}]} numberOfLines={1}>{c.name}</Text>
      <Text style={[s.pickMeta,on&&{color:'#D6E2FF'}]}>{c.goal_count} 个目标 · {c.attempt_count} 次练习{c.due_today?' · '+c.due_today+' 待复习':''}</Text>
     </Pressable>;
    })}
   </ScrollView>
  </View>
 }

 function Home(){
  return <>
   <View style={s.hero}>
    <Text style={s.heroKicker}>TODAY'S LEARNING</Text>
    <Text style={s.heroTitle}>{data?.course?.name||'正在载入课程'}</Text>
    <Text style={s.heroSub}>{tasks.length?`${tasks.length} 个学习目标 · ${dueCount||0} 个建议今天复习`:'先创建第一个学习目标，规划今天的主动学习。'}</Text>
   </View>

   <SectionHead index="1" title="先选一门课" desc="所有目标、资料与练习都归属到当前课程"/>
   <View style={s.pickerInsetHome}><CoursePicker/></View>
   <Pressable accessibilityRole="button" accessibilityLabel="创建新课程" onPress={()=>requireLogin(async()=>{await refresh();setCourseName('');setModal('newcourse')})} style={s.createCourse}>
    <View style={s.createIcon}><Ionicons name="add" size={20} color="#2E6BE6"/></View>
    <View style={{flex:1}}><Text style={s.createTitle}>创建新课程</Text><Text style={s.createMeta}>新目标与资料归入新课程</Text></View>
    <Ionicons name="chevron-forward" size={18} color="#B9C0CC"/>
   </Pressable>

   <Card style={s.statCard}>
    <View style={s.statRow}>
     <Stat label="学习目标" value={current?current.goal_count:tasks.length} accent/>
     <Stat label="今日待复习" value={current?current.due_today:0} accent/>
     <Stat label="累计练习" value={current?current.attempt_count:0}/>
     <Stat label="错题" value={current?current.mistake_count:(data?.mistakes||[]).length}/>
    </View>
    <View style={s.btnRow}>
     <Btn title="新建学习目标" variant="primary" icon="add" disabled={busy||!data} onPress={()=>requireLogin(async()=>{await refresh();clear();setModal('goal')})}/>
     <Btn title="开始复习" icon="play" disabled={busy||!tasks.length} onPress={()=>requireLogin(()=>start(tasks[0]?.id||''))}/>
    </View>
   </Card>

   <SectionHead index="2" title="这门课下的目标" desc="按复习时间排序 · 展开可看每一次练习记录"/>
   {!tasks.length&&<Card><Text style={s.body}>还没有学习目标。新建一个知识点目标，AI 会按到期时间安排练习。</Text><Btn title="新建学习目标" variant="primary" disabled={busy||!data} onPress={()=>requireLogin(async()=>{await refresh();clear();setModal('goal')})}/></Card>}
   {tasks.map(g=>{
    const hist=(goalsById[g.id]||[]).slice().reverse();
    const acc=g.recent_accuracy;
    const open=openGoal===g.id;
    const overdue=g.due&&g.due<=today;
    return <Card key={g.id}>
     <View style={s.goalHead}>
      <Text style={s.goalTitle}>{g.concept}</Text>
      <Pill text={g.level} tone={g.level==='尚未评估'?'soft':g.level==='需要巩固'?'warn':'ok'}/>
     </View>
     <Text style={s.goalTarget}>{g.target}</Text>
     <View style={s.goalStats}>
      <Text style={s.goalStat}><Text style={s.goalStatNum}>{g.attempts||0}</Text> 次练习</Text>
      <Text style={s.goalStat}><Text style={s.goalStatNum}>{acc==null?'—':Math.round(acc*100)+'%'}</Text> 近期正确率</Text>
      <Text style={[s.goalStat,overdue&&{color:'#9A4A1E'}]}>{dueLabel(g.due)}</Text>
     </View>
     <Bar ratio={acc==null?0:acc}/>
     <View style={s.btnRow}>
      <Btn title="开始这一项" variant="primary" icon="play" disabled={busy} onPress={()=>act(()=>start(g.id))}/>
      <Btn title={open?'收起记录':'这 '+hist.length+' 次记录'} icon={open?'chevron-up':'list'} onPress={()=>setOpenGoal(open?'':g.id)}/>
     </View>
     {open&&<View style={s.history}>
      {!hist.length&&<Text style={s.muted}>这个目标还没有练习记录。</Text>}
      {[['correct','答对',hist.filter(h=>h.evaluation?.verdict==='correct')],
        ['incorrect','答错',hist.filter(h=>h.evaluation?.verdict!=='correct')]].map(([tone,label,list])=>{
       if(!list.length)return null;
       return <View key={tone} style={s.historyGroup}>
        <View style={s.historyGroupHead}>
         <Pill text={label+' '+list.length+' 次'} tone={tone==='correct'?'ok':'warn'}/>
        </View>
        {list.map((h,i)=><View key={h.id||i} style={s.historyItem}>
         <MathText text={h.question||'历史题目'}/><View style={s.historyHead}>
          <Text style={s.muted}>{(h.created||'').slice(0,16).replace('T',' ')}</Text>
          {tone!=='correct'&&!!h.error_type&&<Text style={s.historyErr}>错因：{({concept:'概念理解',condition:'适用条件',calculation:'计算过程',memory:'知识记忆',none:'待分析'}[h.error_type]||'待分析')}</Text>}
         </View>
         {!!h.options?.length&&<View style={s.optList}>
          {h.options.map((o,j)=>{
           const key=String.fromCharCode(65+j)+'. ';
           const mine=(h.answer||'').startsWith(key);
           const match=(h.reference||'').trim().match(/^(?:正确答案[：:]?\s*|答案[：:]?\s*)?([A-D])(?:[.、：:\s]|$)/i);
           const right=match?match[1].toUpperCase()===String.fromCharCode(65+j):h.evaluation?.verdict==='correct'&&mine;
           return <View key={j} style={[s.optRow,right&&s.optRight,mine&&!right&&s.optWrong,mine&&right&&s.optMine]}>
            <Text style={s.optKey}>{key}</Text><MathText text={o}/>
            {right&&<Text style={s.optTag}>{mine?'正确答案 · 我的选择':'正确答案'}</Text>}
            {mine&&!right&&<Text style={s.optTagWrong}>我的选择</Text>}
           </View>;
          })}
         </View>}
         {!h.options?.length&&!!h.answer&&<Text style={s.historyAnswer}>我的回答：{h.answer}</Text>}<MathText text={h.evaluation?.explanation||''}/>{!!h.reference&&<MathText text={'参考答案：'+h.reference}/>}
        </View>)}
       </View>;
      })}
     </View>}
    </Card>
   })}

   <SectionHead index="3" title="知识点总结" desc="依据当前课程资料与学习目标整理"/>
   <Card>
    <Text style={s.body}>整理核心概念、公式条件与易错点。资料较长时本次处理前约 15000 字。</Text>
    <Btn title="AI 总结知识点" disabled={busy||!data} onPress={()=>act(async()=>{await api('/lite/summaries',{course_id:course});await refresh();setNote('知识点总结已保存')})}/>
    {!data?.summaries?.length&&<Text style={s.muted}>还没有总结。</Text>}
    {(data?.summaries||[]).map(item=><View key={item.id} style={s.summary}>
     <Text style={s.h2}>{item.payload.title}</Text>
     <Text style={s.muted}>{item.created} UTC · {item.payload.needs_verification?'通用知识总结':'依据课程资料'}</Text>
     {item.payload.key_points.map((x,i)=><MathText key={'k'+i} text={'• '+x}/>)}
     {!!item.payload.formulas.length&&<Text style={s.h2}>公式与条件</Text>}
     {item.payload.formulas.map((x,i)=><MathText key={'f'+i} text={x}/>)}
     {!!item.payload.pitfalls.length&&<Text style={s.h2}>易错点</Text>}
     {item.payload.pitfalls.map((x,i)=><MathText key={'p'+i} text={'• '+x}/>)}
    </View>)}
   </Card>
  </>
 }

 return <SafeAreaView style={s.safe}>
  <View style={s.shell}>
   <View style={s.top}>
    <View style={s.brandRow}><View style={s.brandDot}/><Text style={s.brand}>NotePilot</Text></View>
    <Text style={s.muted}>{data?.model?.configured?data.model.model:'免登录学习空间'}</Text>
   </View>
   <ScrollView contentContainerStyle={s.content} keyboardShouldPersistTaps="handled">
    {busy&&<View style={s.loading}><ActivityIndicator color="#2E6BE6"/><Text style={s.muted}>正在加载，免费服务首次唤醒可能需要等待…</Text></View>}
    {!!error&&<View style={s.alert}><Text accessibilityRole="alert" style={s.error}>{error}</Text><Btn title="重新连接" disabled={busy} onPress={()=>act(refresh)}/></View>}
    {!!note&&<Pressable onPress={()=>setNote('')}><Text style={s.note}>ℹ {note} ×</Text></Pressable>}

    {tab==='首页'&&<Home/>}

    {tab==='AI练习'&&<>
     <View style={s.hero}><Text style={s.heroKicker}>ASK · THINK · REFLECT</Text><Text style={s.heroTitle}>先想一想，再向前一步。</Text></View>
     {!question&&<Card>
      <Text style={s.body}>优先选择到期任务；也可选择知识点。教材文字与回答将发送至 {data?.model?.provider||'文本模型'} 生成反馈；没有资料依据时提示核实。</Text>
      <Btn title="由 Planner 安排练习" variant="primary" disabled={busy} onPress={()=>requireLogin(()=>start(''))}/>
      {tasks.map(g=><Pressable key={g.id} accessibilityRole="button" disabled={busy} onPress={()=>act(()=>start(g.id))} style={s.goalPick}>
       <Text style={s.goalPickTitle}>{g.concept}</Text><Text style={s.goalPickMeta}>{g.target} · 已练 {g.attempts||0} 次</Text>
      </Pressable>)}
     </Card>}
     {question&&<Card>
      <MathText text={question.question}/>
      <Btn title={hint?'收起提示':'给我一点提示'} icon="bulb" onPress={()=>setHint(!hint)}/>
      {hint&&<MathText text={question.hint}/>}
      <Text style={s.muted}>{question.question_type==='single_choice'?'单项选择题 · 请选择一个答案':'简答题 · 用自己的话回答'}</Text>
      {question.question_type==='single_choice'?question.options.map((option,i)=>{const value=String.fromCharCode(65+i)+'. '+option;return <Pressable key={i} accessibilityRole="radio" accessibilityLabel={value} accessibilityState={{checked:answer===value,disabled:busy||!!feedback}} disabled={busy||!!feedback} onPress={()=>setAnswer(value)} style={[s.opt,answer===value&&s.optOn]}><MathText text={(answer===value?'✓ ':'')+value}/></Pressable>}):<Input placeholder="用自己的话回答" multiline value={answer} onChangeText={setAnswer}/>}
      <Btn title="提交回答并更新复习" variant="primary" disabled={busy||!answer.trim()||!!feedback} onPress={()=>act(async()=>{setFeedback(await api('/lite/questions/'+question.id+'/answer',{answer}));await refresh()})}/>
      {feedback&&<>
       <View style={s.feedbackHead}><Pill text={{correct:'正确',incorrect:'错误'}[feedback.evaluation.verdict]} tone={feedback.evaluation.verdict==='correct'?'ok':'warn'}/><Text style={s.muted}>本次已计入复习计划</Text></View>
       <MathText text={feedback.evaluation.explanation}/>
       <Text style={s.muted}>{feedback.evaluation.verdict==='incorrect'?('错因：'+({concept:'概念理解',condition:'适用条件',calculation:'计算过程',memory:'知识记忆',none:'请查看解析'}[feedback.evaluation.error_type]||'请查看解析')+'。'):''}不凭一道题判断完全掌握。</Text>
       {feedback.evaluation.evidence&&<MathText text={'依据：'+feedback.evaluation.evidence}/>}
       {question.question_type!=='single_choice'&&<><MathText text={feedback.evaluation.follow_up}/><Btn title="继续针对性追问" disabled={busy} onPress={()=>act(async()=>{setQuestion(await api('/lite/answers/'+feedback.id+'/follow-up',{}));setAnswer('');setFeedback(null);setHint(false)})}/></>}
       <View style={s.btnRow}><Btn title="下一题" variant="primary" disabled={busy} onPress={()=>act(()=>start(question.goal_id||''))}/><Btn title="保存到错题本" icon="bookmark" onPress={()=>act(async()=>{await api('/lite/answers/'+feedback.id+'/mistake',{});setNote('已保存到错题本');await refresh()})}/></View>
      </>}
      <Text style={s.h2}>本次学习路径</Text>
      {(feedback?.trace||question.trace).map((t,i)=><Text key={i} style={s.muted}>{t.agent} · {t.decision||t.rule||'模型结果已通过结构校验'}</Text>)}
     </Card>}
    </>}

    {tab==='错题本'&&<>
     <View style={s.hero}><Text style={s.heroKicker}>MAKE MISTAKES MATTER</Text><Text style={s.heroTitle}>把错因，变成下一步。</Text></View>
     <Btn title="手动录入错题" variant="primary" icon="add" onPress={()=>requireLogin(async()=>{clear();setModal('mistake')})}/>
     {!data?.mistakes.length&&<Card><Text style={s.body}>暂无错题。可以手动输入，或从练习反馈保存。</Text></Card>}
     {data?.mistakes.map(m=><Card key={m.id}>
      <Text style={s.goalTitle}>{m.concept}</Text>
      <MathText text={m.question}/>
      <MathText text={'我的答案：'+m.answer}/>
      {!!m.analysis&&<MathText text={JSON.parse(m.analysis).explanation}/>}
      <View style={s.btnRow}>
       <Btn title="AI 分析错因" disabled={busy} onPress={()=>act(async()=>{await api('/lite/mistakes/'+m.id+'/analyze',{});await refresh()})}/>
       <Btn title="编辑" variant="ghost" onPress={()=>{setEditId(m.id);setConcept(m.concept);setTarget(m.question);setAnswer(m.answer);setSource(m.source);setModal('mistake')}}/>
       <Btn title="删除…" variant="ghost" onPress={()=>{setEditId(m.id);setModal('delete')}}/>
      </View>
     </Card>)}
    </>}

    {tab==='我的'&&<>
     <View style={s.hero}><Text style={s.heroKicker}>SETTINGS & DATA</Text><Text style={s.heroTitle}>按自己的节奏学习。</Text></View>
     <Card>
      <View style={s.cardHead}>
       <View style={{flex:1}}><Text style={s.h2}>我的课程</Text><Text style={s.body}>切换课程，或管理课程名称。</Text></View>
       <Pressable accessibilityRole="button" accessibilityLabel="创建新课程" onPress={()=>requireLogin(async()=>{await refresh();setCourseName('');setModal('newcourse')})} style={s.addSquare}>
        <Ionicons name="add" size={22} color="#2E6BE6"/>
       </Pressable>
      </View>
      <View style={s.pickerInset}><CoursePicker/></View>      {(data?.courses||[]).filter(c=>c.id===course).map(c=><Pressable key={c.id} accessibilityRole="button" accessibilityLabel="改名或删除当前课程" onPress={()=>{setManageCourse(c);setRename(c.name);setModal('course')}} style={s.manageCourse}>
       <Ionicons name="settings-outline" size={17} color="#6B7280"/>
       <Text style={s.manageCourseText}>改名 / 删除「{c.name}」</Text>
      </Pressable>)}
      <View style={s.divider}/>
      <Text style={s.h2}>学习进度</Text>
      <View style={s.progressRow}>
       <Text style={s.progressNum}>{progressPct}<Text style={s.progressPct}>%</Text></Text>
       <Text style={s.progressMeta}>{masteredCount} / {tasks.length} 个目标已较稳定 · 累计 {data?.attempt_count||0} 次练习</Text>
      </View>
      <Bar ratio={progressPct/100}/>
      <Text style={s.muted}>连续答对 3 次以上才算较稳定；一次答对不视为完全掌握。</Text>
     </Card>
     <Card>
      <Text style={s.h2}>我的教材</Text>
      <Text style={s.body}>上传文字版 PDF / TXT / MD，提取文字供目标与练习引用。PDF 最多 150 页，单文件 20 MB；总结和出题每次最多使用约 15000 字，长教材请按章节拆分。纯扫描件暂不支持。</Text>
      <View style={s.bookGrid}>
       {(data?.documents||[]).map(d=><View key={d.id} style={s.bookItem}>
        <Pressable accessibilityRole="button" accessibilityLabel={'查看资料 '+d.name} disabled={busy||!d.page_count} onPress={()=>act(async()=>{const p=await api('/documents/'+d.id+'/pages/1');setPage(p);setPageEdit(p.text);setModal('page')})}>
         {d.preview?<Image source={{uri:d.preview}} resizeMode="cover" style={s.bookCover}/>:<View style={[s.bookCover,s.bookCoverEmpty]}><Ionicons name="document-text-outline" size={26} color="#B9C0CC"/></View>}
        </Pressable>
        <Text style={s.bookName} numberOfLines={2}>{d.name}</Text>
        <Text style={s.bookMeta}>{d.status==='failed'?(d.error||'解析失败'):d.readable_pages?`${d.readable_pages} 页 · 可学习`:d.status==='completed'?'没有可提取文字':'正在提取文字'}</Text>
        {d.status==='failed'&&<Btn title="重试提取" variant="ghost" disabled={busy} onPress={()=>act(async()=>{await api('/documents/'+d.id+'/process',{});await refresh();setNote('已重新提交，请稍后刷新资料')})}/>}
       </View>)}
       <Pressable accessibilityRole="button" accessibilityLabel="上传教材" disabled={busy} onPress={()=>requireLogin(documents)} style={s.bookUpload}>
        <Ionicons name="add" size={26} color="#8E97A3"/>
        <Text style={s.bookUploadText}>上传教材</Text>
       </Pressable>
      </View>
      <Btn title="刷新资料" variant="ghost" disabled={busy} onPress={()=>requireLogin(refresh)}/>
     </Card>
     <Card>
      <Text style={s.h2}>连接与数据</Text>
      <Input placeholder="服务地址" value={host} onChangeText={setHost}/>
      <Text style={s.muted}>{data?.model.configured?`文本模型：${data.model.model}`:'文本模型尚未配置'} · 本浏览器独立保存学习空间；请允许 Cookie。免费服务更新可能清空记录，建议及时导出。</Text>
      <Btn title="导出数据" onPress={()=>requireLogin(async()=>{const d=await api('/export');if(Platform.OS==='web'){const u=URL.createObjectURL(new Blob([JSON.stringify(d,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=u;a.download='NotePilot-Lite.json';a.click();URL.revokeObjectURL(u)}else{setPageEdit(JSON.stringify(d,null,2));setModal('export')}})}/>
     </Card>
    </>}
   </ScrollView>
   <View style={s.nav}>{tabs.map(([name,icon])=><Pressable key={name} accessibilityRole="tab" accessibilityLabel={name} onPress={()=>setTab(name)} style={s.navItem}>
    <Ionicons name={icon} size={22} color={tab===name?'#2E6BE6':'#9AA3AF'}/><Text style={[s.navText,tab===name&&{color:'#2E6BE6',fontWeight:'600'}]}>{name}</Text>
   </Pressable>)}</View>
  </View>

  <Modal visible={!!modal} animationType="slide" onRequestClose={()=>setModal('')}>
   <SafeAreaView style={s.safe}>
    <View style={s.top}><Text style={s.brand}>{modal==='goal'?'新建学习目标':modal==='newcourse'?'创建课程':modal==='mistake'?'错题':modal==='course'?'管理课程':modal==='delete'?'删除错题':modal==='page'?'资料文字':'导出数据'}</Text><Pressable accessibilityRole="button" accessibilityLabel="关闭" onPress={()=>setModal('')}><Ionicons name="close" size={24} color="#6B7280"/></Pressable></View>
    <ScrollView contentContainerStyle={s.content} keyboardShouldPersistTaps="handled">
     {!!error&&<Text style={s.error}>{error}</Text>}
     {busy&&<ActivityIndicator color="#2E6BE6"/>}

     {modal==='newcourse'&&<Card>
      <Text style={s.h2}>新课程名称</Text>
      <Input placeholder="如：流体力学（下）" value={courseName} onChangeText={setCourseName}/>
      <Text style={s.body}>创建后会自动切换到新课程，之后新建的目标与上传的资料都归入它。</Text>
      <Btn title="创建课程" variant="primary" disabled={busy||!courseName.trim()} onPress={()=>act(async()=>{const c=await api('/courses',{name:courseName.trim()});setCourse(c.id);setCourseName('');setModal('')})}/>
     </Card>}

     {modal==='goal'&&<Card>
      <Text style={s.body}>新目标将加入课程「{data?.course?.name||''}」。</Text>
      <Text style={s.h2}>知识点</Text>
      <Input placeholder="想学习的知识点，如伯努利方程" value={concept} onChangeText={setConcept}/>
      <Text style={s.h2}>学习目标</Text>
      {goalOptions.map(option=><Pressable key={option} accessibilityRole="radio" accessibilityState={{checked:goalTarget===option}} onPress={()=>setGoalTarget(option)} style={[s.opt,goalTarget===option&&s.optOn]}><Text style={s.bt}>{goalTarget===option?'✓ ':''}{option}</Text></Pressable>)}
      <Text style={s.h2}>学习依据</Text>
      <Text style={s.body}>选择已有资料或上传文件，自动读取文字，无需填写教材原文。</Text>
      <Btn title={(documentId===''?'✓ ':'')+'自动使用当前课程资料'} onPress={()=>setDocumentId('')}/>
      {(data?.documents||[]).map(d=><Btn key={d.id} title={(documentId===d.id?'✓ ':'')+d.name+(d.readable_pages?'':'（暂无可用文字）')} disabled={busy||!d.readable_pages} onPress={()=>setDocumentId(d.id)}/>)}
      <Btn title="上传 PDF / TXT / MD" variant="ghost" disabled={busy} onPress={()=>act(async()=>{const id=await documents();if(id)setDocumentId(id)})}/>
      {!data?.documents.length&&<Text style={s.muted}>尚无资料。可先创建目标；无教材依据时，AI 内容会提示需要核实。纯扫描 PDF 暂不支持文字提取。</Text>}
      <Btn title="保存学习目标" variant="primary" disabled={busy||!concept.trim()} onPress={()=>act(async()=>{await api('/lite/goals',{course_id:course,concept,target:goalTarget,document_id:documentId});setModal('');clear();await refresh()})}/>
     </Card>}

     {modal==='mistake'&&<Card>
      <Text style={s.h2}>知识点</Text><Input placeholder="知识点" value={concept} onChangeText={setConcept}/>
      <Text style={s.h2}>题目</Text><Input placeholder="题目" multiline value={target} onChangeText={setTarget}/>
      <Text style={s.h2}>我的答案</Text><Input placeholder="我的答案" multiline value={answer} onChangeText={setAnswer}/>
      <Text style={s.h2}>课程依据（选填）</Text><Input placeholder="课程依据（选填）" multiline value={source} onChangeText={setSource}/>
      <Btn title="保存" variant="primary" disabled={busy||!concept.trim()||!target.trim()} onPress={()=>act(async()=>{await api('/lite/mistakes'+(editId?'/'+editId:''),{course_id:course,concept,question:target,answer,source},editId?'PUT':'POST');setModal('');clear();await refresh()})}/>
     </Card>}

     {modal==='course'&&manageCourse&&<Card>
      <Text style={s.h2}>课程名称</Text>
      <Input placeholder="课程名称" value={rename} onChangeText={setRename}/>
      <Btn title="保存新名称" variant="primary" disabled={busy||!rename.trim()} onPress={()=>act(async()=>{await api('/courses/'+manageCourse.id,{name:rename.trim(),exam_date:manageCourse.exam_date||null},'PUT');setModal('');await refresh()})}/>
      <View style={s.divider}/>
      <Text style={s.h2}>删除课程</Text>
      <Text style={s.body}>{otherCourses.length?`删除课程「${manageCourse.name}」，其资料、目标、错题与练习记录将保留到「${otherCourses[0].name}」，不删除学习内容。`:'至少保留一门课程，暂不能删除。'}</Text>
      <Btn title="删除课程" variant="ghost" disabled={busy||!otherCourses.length} onPress={()=>act(async()=>{await api('/courses/'+manageCourse.id+'/merge',{target_id:otherCourses[0].id});setModal('');if(course===manageCourse.id)setCourse(otherCourses[0].id);else await refresh()})}/>
     </Card>}

     {modal==='delete'&&<Card>
      <Text style={s.body}>确认删除这条错题？此操作不能撤销。</Text>
      <Btn title="确认删除" variant="primary" onPress={()=>act(async()=>{await api('/lite/mistakes/'+editId,null,'DELETE');setModal('');await refresh()})}/>
     </Card>}

     {modal==='page'&&page&&<Card>
      <Text style={s.goalTitle}>{page.name} · 第 {page.number} 页</Text>
      {[page.number-1,page.number+1].filter(n=>n>=1&&n<=(data?.documents.find(d=>d.id===page.document_id)?.page_count||1)).map(n=><Btn key={n} title={'查看第 '+n+' 页'} onPress={()=>act(async()=>{const p=await api('/documents/'+page.document_id+'/pages/'+n);setPage(p);setPageEdit(p.text)})}/>)}
      {page.preview&&<Image source={{uri:page.preview}} resizeMode="contain" style={{width:'100%',height:320,borderRadius:16,marginVertical:12}}/>}
      <MathText text={pageEdit}/>
      <Input placeholder="资料文字，可手动补充扫描页内容" multiline value={pageEdit} onChangeText={setPageEdit}/>
      <Btn title="保存资料校正" variant="primary" onPress={()=>act(async()=>{await api('/documents/'+page.document_id+'/pages/'+page.number,{text:pageEdit},'PUT');setNote('已保存')})}/>
     </Card>}

     {modal==='export'&&<Input placeholder="导出内容" multiline value={pageEdit} onChangeText={setPageEdit}/>}
    </ScrollView>
   </SafeAreaView>
  </Modal>
 </SafeAreaView>
}

const BLUE='#2E6BE6',INK='#151B26',MUTED='#6B7280';
const s=StyleSheet.create({
 safe:{flex:1,backgroundColor:'#F7F6F2'},
 shell:{flex:1,maxWidth:760,width:'100%',alignSelf:'center'},
 top:{paddingHorizontal:20,paddingVertical:14,flexDirection:'row',justifyContent:'space-between',alignItems:'center'},
 brandRow:{flexDirection:'row',alignItems:'center',gap:8},
 brandDot:{width:10,height:10,borderRadius:5,backgroundColor:BLUE},
 brand:{fontSize:19,fontWeight:'700',color:INK,letterSpacing:.3},
 content:{padding:20,paddingBottom:20,gap:0},
 hero:{paddingTop:8,paddingBottom:18},
 heroKicker:{fontSize:11,color:BLUE,letterSpacing:2.4,marginBottom:10},
 heroTitle:{fontSize:32,lineHeight:42,fontWeight:'700',color:INK},
 heroSub:{fontSize:14,color:MUTED,lineHeight:24,marginTop:8},
 secHead:{flexDirection:'row',alignItems:'center',gap:12,marginTop:28,marginBottom:12},
 secNum:{width:26,height:26,borderRadius:13,backgroundColor:BLUE,alignItems:'center',justifyContent:'center'},
 secNumText:{color:'#FFFFFF',fontSize:13,fontWeight:'700'},
 secTitle:{fontSize:19,fontWeight:'700',color:INK},
 secDesc:{fontSize:12.5,color:MUTED,marginTop:3,lineHeight:19},
 card:{padding:20,backgroundColor:'#FFFFFF',borderRadius:20,marginBottom:12,borderWidth:1,borderColor:'#EAE6DC'},
 statCard:{paddingVertical:22},
 statRow:{flexDirection:'row',justifyContent:'space-between'},
 stat:{flex:1,alignItems:'center'},
 statValue:{fontSize:24,fontWeight:'700',color:INK},
 statLabel:{fontSize:11.5,color:MUTED,marginTop:4},
 btnRow:{flexDirection:'row',flexWrap:'wrap',gap:8,marginTop:16},
 btn:{flexDirection:'row',alignItems:'center',justifyContent:'center',gap:6,paddingHorizontal:16,paddingVertical:12,borderRadius:12,marginVertical:4},
 btnSoft:{backgroundColor:'#EEF3FF'},
 btnPrimary:{backgroundColor:BLUE},
 btnGhost:{backgroundColor:'transparent',borderWidth:1,borderColor:'#E3DFD4'},
 bt:{color:BLUE,fontWeight:'600',fontSize:14,textAlign:'center'},
 title:{fontSize:30,lineHeight:42,fontWeight:'700',color:INK,marginVertical:16},
 h2:{fontSize:16,fontWeight:'700',color:INK,lineHeight:26,marginTop:14,marginBottom:2},
 body:{fontSize:14,color:MUTED,lineHeight:24,marginVertical:8},
 muted:{fontSize:12,color:MUTED,lineHeight:20,marginVertical:4},
 error:{color:'#9A4A1E',padding:10,lineHeight:22},
 note:{backgroundColor:'#EEF3FF',color:BLUE,padding:12,borderRadius:12,fontSize:13,lineHeight:20,overflow:'hidden'},
 alert:{backgroundColor:'#FDF1E8',borderRadius:14,padding:14,marginBottom:8},
 loading:{flexDirection:'row',alignItems:'center',gap:10,marginBottom:10},
 pickerWrap:{marginBottom:0},
 pickerRow:{gap:10,paddingRight:8},
 pickerInset:{marginRight:-20,marginTop:2},
 pickerInsetHome:{marginRight:-20},
 pickCard:{backgroundColor:'#FFFFFF',borderRadius:16,paddingHorizontal:18,paddingVertical:14,borderWidth:1,borderColor:'#EAE6DC',minWidth:190},
 pickCardOn:{backgroundColor:BLUE,borderColor:BLUE},
 pickName:{fontSize:16,fontWeight:'700',color:INK},
 pickMeta:{fontSize:12,color:MUTED,marginTop:4},
 goalHead:{flexDirection:'row',alignItems:'center',justifyContent:'space-between',gap:10},
 goalTitle:{fontSize:17.5,fontWeight:'700',color:INK,lineHeight:26,flex:1},
 goalTarget:{fontSize:13.5,color:MUTED,lineHeight:22,marginTop:6},
 goalStats:{flexDirection:'row',flexWrap:'wrap',gap:14,marginTop:12},
 goalStat:{fontSize:12.5,color:MUTED},
 goalStatNum:{fontSize:15,fontWeight:'700',color:INK},
 bar:{height:5,borderRadius:3,backgroundColor:'#EFECE3',marginTop:12,overflow:'hidden'},
 barFill:{height:5,borderRadius:3,backgroundColor:BLUE},
 pill:{paddingHorizontal:10,paddingVertical:4,borderRadius:999,alignSelf:'flex-start'},
 pillSoft:{backgroundColor:'#F1EEE5'},
 pillBlue:{backgroundColor:'#EEF3FF'},
 pillWarn:{backgroundColor:'#FBEADF'},
 pillOk:{backgroundColor:'#E2F1EA'},
 pillText:{fontSize:11.5,color:MUTED,fontWeight:'600'},
 history:{marginTop:14,borderTopWidth:1,borderTopColor:'#EFECE3',paddingTop:12},
 historyGroup:{marginBottom:10},
 historyGroupHead:{flexDirection:'row',alignItems:'center',marginBottom:4},
 historyItem:{paddingVertical:10,borderBottomWidth:1,borderBottomColor:'#F4F1E9'},
 historyHead:{flexDirection:'row',alignItems:'center',gap:10,justifyContent:'space-between'},
 historyErr:{fontSize:12,color:'#9A4A1E'},
 historyAnswer:{fontSize:13,color:INK,lineHeight:21,marginTop:6},
 optList:{marginTop:8,gap:6},
 optRow:{flexDirection:'row',alignItems:'center',gap:8,paddingHorizontal:12,paddingVertical:9,borderRadius:10,backgroundColor:'#F7F6F2'},
 optRight:{backgroundColor:'#EDF7F1'},
 optWrong:{backgroundColor:'#FBEEE6'},
 optMine:{borderWidth:1,borderColor:'#2E6BE6'},
 optKey:{fontSize:13,fontWeight:'700',color:MUTED},
 optTag:{fontSize:11,color:'#1F7A5A',fontWeight:'600',marginLeft:'auto'},
 optTagWrong:{fontSize:11,color:'#9A4A1E',fontWeight:'600',marginLeft:'auto'},
 pickAdd:{width:28,height:28,borderRadius:14,backgroundColor:'#EEF3FF',alignItems:'center',justifyContent:'center',marginBottom:8},
 createCourse:{flexDirection:'row',alignItems:'center',gap:12,padding:14,borderRadius:16,backgroundColor:'#F7F6F2',borderWidth:1,borderColor:'#E7E3D9',marginTop:12,marginBottom:12},
 createIcon:{width:32,height:32,borderRadius:10,backgroundColor:'#EEF3FF',alignItems:'center',justifyContent:'center'},
 cardHead:{flexDirection:'row',alignItems:'flex-start',gap:12},
 addSquare:{width:36,height:36,borderRadius:12,backgroundColor:'#EEF3FF',alignItems:'center',justifyContent:'center'},
 createTitle:{fontSize:15,fontWeight:'700',color:INK},
 createMeta:{fontSize:12,color:MUTED,marginTop:2},
 manageCourse:{flexDirection:'row',alignItems:'center',gap:8,paddingVertical:12,paddingHorizontal:4},
 manageCourseText:{fontSize:13,color:MUTED},
 divider:{height:1,backgroundColor:'#EFECE3',marginVertical:18},
 progressRow:{flexDirection:'row',alignItems:'flex-end',gap:12,marginBottom:6},
 progressNum:{fontSize:34,fontWeight:'700',color:BLUE,lineHeight:40},
 progressPct:{fontSize:18,fontWeight:'600'},
 progressMeta:{fontSize:13,color:MUTED,lineHeight:20,paddingBottom:6},
 bookGrid:{flexDirection:'row',flexWrap:'wrap',gap:14,marginVertical:14},
 bookItem:{width:132},
 bookCover:{width:132,height:178,borderRadius:10,backgroundColor:'#EDEBE4',borderWidth:1,borderColor:'#E2DED3'},
 bookCoverEmpty:{alignItems:'center',justifyContent:'center'},
 bookName:{fontSize:13,color:INK,lineHeight:19,marginTop:8},
 bookMeta:{fontSize:11.5,color:MUTED,lineHeight:18,marginTop:2},
 bookUpload:{width:132,height:178,borderRadius:10,borderWidth:1.5,borderStyle:'dashed',borderColor:'#C9C3B6',alignItems:'center',justifyContent:'center',gap:6},
 bookUploadText:{fontSize:13,color:MUTED},
 summary:{marginTop:14,borderTopWidth:1,borderTopColor:'#EFECE3',paddingTop:10},
 opt:{paddingHorizontal:16,paddingVertical:13,backgroundColor:'#F7F5EF',borderRadius:12,marginVertical:5,borderWidth:1,borderColor:'transparent'},
 optOn:{borderColor:BLUE,backgroundColor:'#EEF3FF'},
 goalPick:{backgroundColor:'#F7F5EF',borderRadius:12,padding:14,marginVertical:5},
 goalPickTitle:{fontSize:15,fontWeight:'700',color:INK},
 goalPickMeta:{fontSize:12,color:MUTED,marginTop:3},
 feedbackHead:{flexDirection:'row',alignItems:'center',gap:10,marginTop:16},
 courseRow:{flexDirection:'row',alignItems:'center',gap:10,marginVertical:6},
 courseName:{flex:1,padding:14,borderRadius:14,backgroundColor:'#F7F5EF'},
 courseNameOn:{backgroundColor:BLUE},
 courseNameText:{fontSize:15.5,fontWeight:'700',color:INK},
 courseNameMeta:{fontSize:12,color:MUTED,marginTop:3},
 docRow:{borderTopWidth:1,borderTopColor:'#F1EEE5',paddingTop:12,marginTop:12},
 input:{backgroundColor:'#F7F5EF',borderWidth:1,borderColor:'#E7E3D9',borderRadius:12,padding:13,color:INK,marginVertical:8,fontSize:15},
 nav:{flexDirection:'row',borderTopWidth:1,borderColor:'#EAE6DC',backgroundColor:'#FFFFFF',paddingVertical:10},
 navItem:{flex:1,alignItems:'center',gap:2},
 navText:{fontSize:11.5,color:'#9AA3AF'},
});
