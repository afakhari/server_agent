import { useCallback, useEffect, useMemo, useState } from 'react';
import type { AppendMessage, ThreadMessageLike } from '@assistant-ui/react';
import { AssistantRuntimeProvider, useExternalStoreRuntime, ThreadPrimitive, MessagePrimitive, ComposerPrimitive, AuiIf } from '@assistant-ui/react';
import { Activity, ArrowUp, BookOpen, CheckCircle2, ChevronDown, CircleAlert, CircleHelp, ClipboardCheck, CloudUpload, FileSearch, History, KeyRound, List, LoaderCircle, Menu, PanelLeftClose, Plus, RefreshCcw, Rocket, Server, ShieldCheck, Sparkles, X } from 'lucide-react';

type UIPayload = { type?: string; [key: string]: any };
type ChatItem = { id: string; role: 'user'|'assistant'; content: string; ui?: UIPayload; at: number };
type Thread = { id: string; project?: string; mode: string; updated_at: number };
const examples = ['سایتم خطای ۵۰۰ می‌دهد', 'پروژه‌ام را روی لیارا منتشر کن', 'فهرست برنامه‌های حساب'];
const uid = () => crypto.randomUUID();
function parseError(response: Response, data: any) {
  return new Error(typeof data?.detail === 'string' ? data.detail : 'خطای ارتباط با سرویس (' + response.status + ')');
}

function Report({data, onApproval}:{data:any;onApproval:(proposal:any,approved:boolean,confirm:string)=>Promise<void>}) {
  const [showEvidence,setShowEvidence] = useState(false);
  const [confirmation,setConfirmation] = useState('');
  const [busy,setBusy] = useState(false);
  const report = data.report || {};
  const proposal = report.proposals?.[0];
  async function act(approved:boolean) {
    if (approved && confirmation !== report.project) return;
    setBusy(true);
    try { await onApproval(proposal,approved,confirmation); }
    finally { setBusy(false); }
  }
  return <div className="toolcard">
    <div className="cardhead"><span><FileSearch size={17}/> گزارش عیب‌یابی</span><span className="tag">{report.mode === 'demo' ? 'شبیه‌سازی' : 'داده زنده'}</span></div>
    <div className="metadata"><span>سرویس: <b dir="ltr">{report.project}</b></span><span>{report.verdict}</span></div>
    {(report.hypotheses || []).map((h:any,i:number)=><div className="hypothesis" key={i}>
      <div className="cardhead"><strong>{h.title}</strong><span className="tag">اطمینان: {h.confidence}</span></div>
      <p>{h.reason}</p><small>شواهد: {(h.evidence_ids||[]).join('، ')||'موجود نیست'}</small>
    </div>)}
    {report.recommendation && <div className="finding"><b>پیشنهاد:</b> {report.recommendation}</div>}
    {report.ai_commentary?.mode === 'advisory-llm' && <p className="advisory"><Sparkles size={14}/> {report.ai_commentary.narrative}</p>}
    <button className="plainbtn" onClick={()=>setShowEvidence(v=>!v)} aria-expanded={showEvidence}><List size={15}/> {showEvidence?'بستن شواهد':'مشاهده شواهد و منابع'} <ChevronDown size={14}/></button>
    {showEvidence && <div className="evidencelist">{(report.evidence||[]).map((ev:any)=><div className="evidence" key={ev.id}><strong dir="ltr">{ev.id}</strong> · {ev.text}<small dir="ltr">{ev.source}</small></div>)}</div>}
    {(report.limitations||[]).length > 0 && <div className="caution">{report.limitations.join(' • ')}</div>}
    {proposal && <div className="approval">
      <div className="cardhead"><strong><ShieldCheck size={17}/> تأیید عملیات حساس</strong><span className="tag warning">ریسک: {proposal.risk}</span></div>
      <p><b>{proposal.title}</b> · {proposal.reason}</p>
      <p>{proposal.impact}</p><small>مجوز سه دقیقه اعتبار دارد و فقط یک بار برای همین سرویس قابل استفاده است.</small>
      <label>برای تأیید، نام سرویس را دقیق وارد کنید <b dir="ltr">{report.project}</b>
        <input value={confirmation} onChange={e=>setConfirmation(e.target.value)} placeholder="نام سرویس" dir="ltr" autoComplete="off" />
      </label>
      <div className="actions"><button className="primary" disabled={busy||confirmation!==report.project} onClick={()=>act(true)}>{busy?'در حال ثبت…':'تأیید و اجرا'}</button><button className="secondary" disabled={busy} onClick={()=>act(false)}>لغو</button></div>
    </div>}
  </div>;
}
function DeployCard({data,token,activeProject,mode}:{data:UIPayload;token:string;activeProject:string;mode:string}) {
  const [path,setPath] = useState('fastapi-shop');
  const [project,setProject] = useState(data.project === 'demo-shop' ? '' : (data.project || activeProject || ''));
  const [platform,setPlatform] = useState(data.scout?.platform || 'python');
  const [port,setPort] = useState(String(data.scout?.port || '8000'));
  const [backend,setBackend] = useState('api-existing');
  const [planId,setPlanId] = useState('');
  const [plan,setPlan] = useState<any>(null);
  const [scan,setScan] = useState<any>(data.scout || null);
  const [confirmation,setConfirmation] = useState('');
  const [result,setResult] = useState<any>(null);
  const [error,setError] = useState('');
  const [busy,setBusy] = useState(false);
  const api = async (url:string,body:any) => {
    const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json','X-Sentinel-Access-Key':token},body:JSON.stringify(body)});
    const json=await r.json(); if(!r.ok) throw parseError(r,json);return json;
  };
  async function run(job:()=>Promise<any>,save:(v:any)=>void) {
    setBusy(true);setError('');
    try {save(await job());}catch(e:any){setError(e.message);}finally{setBusy(false);}
  }
  return <div className="toolcard">
    <div className="cardhead"><strong><CloudUpload size={17}/> استقرار هدایت‌شده</strong><span className="tag">{mode==='demo'?'آزمایش نمایشی':'محیط واقعی محدود'}</span></div>
    {scan && <div className="finding"><b>شناسایی پروژه:</b> {scan.framework} / {scan.platform} · پورت {scan.port}<div className="secondarytext">متغیرهای لازم: {(scan.required_env_names||[]).join('، ')||'گزارش نشده'}</div></div>}
    <div className="formgrid">
      <label>مسیر سورس در فضای کاری مجاز<input value={path} onChange={e=>setPath(e.target.value)} dir="ltr"/></label>
      <label>شناسه برنامه آزمایشی<input value={project} onChange={e=>setProject(e.target.value)} dir="ltr" /></label>
      <label>روش انتشار<select value={backend} onChange={e=>setBackend(e.target.value)}><option value="api-existing">API · برنامه موجود</option><option value="api">API · ساخت برنامه</option><option value="cli">CLI · برنامه موجود</option></select></label>
      <label>پلتفرم<select value={platform} onChange={e=>setPlatform(e.target.value)}><option value="python">Python</option><option value="node">Node</option><option value="php">PHP</option><option value="docker">Docker</option></select></label>
      <label>پورت<input value={port} onChange={e=>setPort(e.target.value)} type="number" min="1" max="65535" dir="ltr"/></label>
      {backend==='api' && <label>شناسه پلن معتبر<input value={planId} onChange={e=>setPlanId(e.target.value)} dir="ltr"/></label>}
    </div>
    <div className="actions">
      <button className="secondary" disabled={busy||mode!=='live'||!token} onClick={()=>run(()=>api('/api/scout',{path}),x=>setScan(x.analysis))}>تحلیل سورس</button>
      <button className="primary" disabled={busy||mode!=='live'||!token||!project||!path} onClick={()=>run(()=>api('/api/deploy/plan',{backend,project,path,platform,port:Number(port),plan_id:backend==='api'?planId:'existing'}),x=>{setPlan(x);setConfirmation('');})}>پیش‌نمایش انتشار</button>
    </div>
    {mode==='demo' && <div className="caution">این نمونه شبیه‌سازی است. عملیات انتشار واقعی فقط با اتصال امن و مجوز سمت سرور فعال می‌شود.</div>}
    {plan && <div className="approval"><strong>پیش‌نمایش عملیات واقعی</strong>
      <p>پروژه: <span dir="ltr">{plan.project}</span> · پلتفرم: {plan.platform} · پورت: {plan.port}</p>
      <p>شناسه پلن: {plan.plan_id||'برنامه موجود'} · قیمت: تأییدنشده</p>
      <p>{plan.warning}</p><small>اثر بر سرویس موجود و هزینه احتمالی را پیش از تأیید بررسی کنید.</small>
      <label>برای تأیید، نام پروژه را وارد کنید<input dir="ltr" value={confirmation} onChange={e=>setConfirmation(e.target.value)} /></label>
      <button className="primary" disabled={busy||confirmation!==plan.project} onClick={()=>run(()=>api('/api/deploy/execute',{proposal_id:plan.proposal_id,confirm_project:plan.project}),setResult)}>تأیید و ارسال انتشار</button>
    </div>}
    {result && <div className="finding"><b>نتیجه ارسال:</b> {JSON.stringify(result)}<p>ارسال انتشار به معنی سلامت تأییدشده نیست. بعد از آن وضعیت انتشار و پروب سلامت را بررسی کنید.</p></div>}
    {error && <div role="alert" className="caution">{error}</div>}
  </div>;
}
function ToolCard({ui,onApproval,onProject,token,project,mode}:{ui?:UIPayload;onApproval:(p:any,a:boolean,c:string)=>Promise<void>;onProject:(p:string)=>void;token:string;project:string;mode:string}) {
  const [listing,setListing] = useState<any[]>([]);
  const [error,setError] = useState('');
  if (!ui?.type) return null;
  if (ui.type==='inspection') return <Report data={ui} onApproval={onApproval}/>;
  if (ui.type==='deploy') return <DeployCard data={ui} token={token} activeProject={project} mode={mode}/>;
  if (ui.type==='execution') return <div className="toolcard"><div className="cardhead"><strong><ClipboardCheck size={17}/> نتیجه عملیات</strong></div>
    <p>ارسال: {ui.result?.execution||'نامشخص'}</p><p>راستی‌آزمایی: {ui.result?.verification||'نامشخص'}</p>
    <p>{ui.result?.message||'اطلاعات بیشتری موجود نیست.'}</p></div>;
  if (ui.type==='projects'||ui.type==='project_picker') {
    const projects = ui.projects || listing;
    return <div className="toolcard"><strong><Server size={17}/> برنامه‌های حساب</strong>
      {projects.length ? projects.map((p:any)=><button className="projectchoice" key={p.name} onClick={()=>onProject(p.name)} dir="ltr">{p.name} <CheckCircle2 size={15}/></button>):<p className="secondarytext">برای مشاهده برنامه‌ها از حساب متصل استفاده کنید.</p>}
      {ui.type==='project_picker' && <button className="secondary" onClick={async()=>{try{const r=await fetch('/api/projects',{headers:{'X-Sentinel-Access-Key':token}});const j=await r.json();if(!r.ok)throw parseError(r,j);setListing((j.projects||[]).map((x:any)=>({name:x.project_id||x.name})));}catch(e:any){setError(e.message)}}}>دریافت فهرست واقعی</button>}
      {error && <p role="alert" className="caution">{error}</p>}
    </div>;
  }
  if(ui.type==='error'||ui.type==='notice')return <p className="caution">{ui.text}</p>;
  return null;
}
async function parseStream(response:Response,onEvent:(event:string,data:any)=>void) {
  if(!response.ok){let json:any={};try{json=await response.json()}catch{}throw parseError(response,json);}
  if(!response.body)throw new Error('پاسخ جریانی در دسترس نیست.');
  const reader=response.body.getReader();const decoder=new TextDecoder();let buffer='';
  while(true){const {done,value}=await reader.read();if(done)break;buffer+=decoder.decode(value,{stream:true}).replace(/\r\n/g,'\n');
    let sep;while((sep=buffer.indexOf('\n\n'))!==-1){const entry=buffer.slice(0,sep);buffer=buffer.slice(sep+2);
      const ev=entry.split('\n').find(x=>x.startsWith('event:'))?.slice(6).trim()||'message';
      const dat=entry.split('\n').filter(x=>x.startsWith('data:')).map(x=>x.slice(5).trim()).join('\n');
      if(dat)onEvent(ev,JSON.parse(dat));
    }
  }
}
export default function App() {
  const [messages,setMessages] = useState<ChatItem[]>([]);
  const [threadId,setThreadId] = useState<string|null>(null);
  const [threads,setThreads] = useState<Thread[]>([]);
  const [mode,setMode] = useState<'demo'|'live'>('demo');
  const [scenario,setScenario] = useState('transient');
  const [project,setProject] = useState('');
  const [token,setToken] = useState('');
  const [running,setRunning] = useState(false);
  const [status,setStatus] = useState('');
  const [sideOpen,setSideOpen] = useState(true);
  const [error,setError] = useState('');
  const [engine,setEngine] = useState('');
  const headers = useMemo(()=>({'Content-Type':'application/json','X-Sentinel-Access-Key':token}),[token]);
  const refreshThreads = useCallback(async()=>{try{const r=await fetch('/api/chat/threads',{headers});if(!r.ok)return;const json=await r.json();setThreads(json.threads||[]);}catch{}},[headers]);
  useEffect(()=>{void refreshThreads();},[refreshThreads]);
  const loadThread = useCallback(async(id:string)=>{
    const r=await fetch('/api/chat/threads/'+encodeURIComponent(id),{headers});
    const data=await r.json();if(!r.ok)throw parseError(r,data);
    setMessages((data.messages||[]).map((m:any)=>({id:m.id,role:m.role,content:m.content,ui:m.ui,at:m.at})));
    setThreadId(id);setMode(data.mode);setProject(data.project||'');setError('');
  },[headers]);
  const send = useCallback(async(input:string)=>{
    if(running||!input.trim())return;
    const item:ChatItem={id:uid(),role:'user',content:input.trim(),at:Date.now()/1000};
    setMessages(old=>[...old,item]);setRunning(true);setError('');setStatus('در حال شروع بررسی...');
    try {
      const response=await fetch('/api/chat/stream',{method:'POST',headers,body:JSON.stringify({message:input,thread_id:threadId,mode,project:project||null,scenario})});
      await parseStream(response,(event,data)=>{
        if(event==='status')setStatus(data.label||'در حال بررسی...');
        if(event==='error')throw new Error(data.detail||'خطا در پردازش');
        if(event==='complete'){
          setThreadId(data.thread_id);setEngine(data.engine||'');setStatus('');
          const reply:ChatItem={id:uid(),role:'assistant',content:data.answer||'',ui:data.ui,at:Date.now()/1000};
          setMessages(old=>[...old,reply]);if(data.ui?.report?.project)setProject(data.ui.report.project);
          void refreshThreads();
        }
      });
    }catch(e:any){setError(e.message);setMessages(old=>[...old,{id:uid(),role:'assistant',content:'درخواست کامل نشد. '+e.message,ui:{type:'error',text:e.message},at:Date.now()/1000}]);}
    finally{setRunning(false);setStatus('');}
  },[running,headers,threadId,mode,project,scenario,refreshThreads]);
  const onNew = useCallback(async(message:AppendMessage)=>{
    const input=message.content.filter((p:any)=>p.type==='text').map((p:any)=>p.text).join('\n');
    await send(input);
  },[send]);
  const runtime = useExternalStoreRuntime({
    messages, isRunning:running, onNew,
    convertMessage:(m:ChatItem):ThreadMessageLike=>({id:m.id,role:m.role,content:[{type:'text',text:m.content}],createdAt:new Date(m.at*1000)})
  });
  const approval = useCallback(async(proposal:any,approved:boolean,confirm:string)=>{
    if(!threadId)throw new Error('گفت‌وگو هنوز شناسه ندارد.');
    const r=await fetch('/api/chat/approval',{method:'POST',headers,body:JSON.stringify({thread_id:threadId,proposal_id:proposal.proposal_id,confirm_project:confirm||project,approved})});
    const data=await r.json();if(!r.ok){setError(data.detail||'تأیید ناموفق بود');throw parseError(r,data);}
    await loadThread(threadId);
  },[threadId,headers,project,loadThread]);
  const onProject=(name:string)=>{setProject(name);setStatus('سرویس '+name+' انتخاب شد. درخواست خود را در چت بنویسید.');};
  function reset(){setMessages([]);setThreadId(null);setProject('');setError('');setStatus('');}
  return <AssistantRuntimeProvider runtime={runtime}>
    <div className="app" dir="rtl">
      <aside className={'sidebar '+(sideOpen?'':'collapsed')}>
        <div className="brand"><div className="brandicon"><Activity size={22}/></div><span><b>LIARA SENTINEL</b><small>دستیار هوشمند زیرساخت</small></span><button className="iconbutton collapse" onClick={()=>setSideOpen(false)} aria-label="بستن نوار کناری"><PanelLeftClose size={18}/></button></div>
        <button className="newchat" onClick={reset}><Plus size={18}/> گفت‌وگوی جدید</button>
        <div className="sidebarlabel"><History size={15}/> گفت‌وگوهای اخیر</div>
        <div className="threadlist">{threads.map(t=><button key={t.id} className={'threadbutton '+(t.id===threadId?'selected':'')} onClick={()=>void loadThread(t.id).catch(e=>setError(e.message))}>
          <span>{t.project || 'گفت‌وگو بدون پروژه'}</span><small dir="ltr">{new Date(t.updated_at*1000).toLocaleDateString('fa-IR')}</small>
        </button>)}</div>
        <div className="sidebarbottom"><ShieldCheck size={15}/> عملیات حساس فقط با تأیید شما</div>
      </aside>
      <main className="main">
        <header className="topbar">
          <div className="topstart">{!sideOpen && <button className="iconbutton" onClick={()=>setSideOpen(true)} aria-label="بازکردن نوار کناری"><Menu size={20}/></button>}<span className="headlogo">Sentinel</span><span className="separator">/</span><span>{project || 'فضای کاری'}</span></div>
          <div className="topend"><span className={'indicator '+mode}></span><select aria-label="محیط اجرا" value={mode} onChange={e=>{setMode(e.target.value as 'demo'|'live');reset();}}><option value="demo">Demo Sandbox</option><option value="live">Live Read / Test</option></select></div>
        </header>
        <div className="utilitybar">
          <label><Server size={15}/> شناسه پروژه<input value={project} onChange={e=>setProject(e.target.value)} placeholder="نام پروژه در لیارا" dir="ltr"/></label>
          {mode==='demo'?<label>سناریو<select value={scenario} onChange={e=>setScenario(e.target.value)}><option value="transient">خرابی فرایند</option><option value="env">متغیر محیطی</option><option value="memory">کمبود حافظه</option><option value="release">خطای انتشار</option><option value="healthy">سالم</option></select></label>:
          <label className="access"><KeyRound size={15}/><input type="password" autoComplete="off" value={token} onChange={e=>setToken(e.target.value)} placeholder="کلید دسترسی Sentinel (نه توکن لیارا)" aria-label="کلید دسترسی Sentinel"/></label>}
          <button className="iconbutton" onClick={()=>void refreshThreads()} title="بروزرسانی تاریخچه"><RefreshCcw size={16}/></button>
        </div>
        <div className="chatregion">
          <ThreadPrimitive.Root className="threadroot">
            <ThreadPrimitive.Viewport className="threadviewport">
              <AuiIf condition={s=>s.thread.isEmpty}>
                <section className="welcome"><div className="welcomemark"><Sparkles size={29}/></div><h1>چطور می‌تونم به سایتت کمک کنم؟</h1>
                  <p>از انتشار اولین نسخه تا تشخیص خطا و بررسی سلامت سرویس؛ هدف خودت را بگو، من مسیر مناسب را پیشنهاد می‌دهم.</p>
                  <div className="suggestions">{examples.map(x=><ThreadPrimitive.Suggestion key={x} prompt={x} send className="suggestion"><ArrowUp size={15}/>{x}</ThreadPrimitive.Suggestion>)}</div>
                </section>
              </AuiIf>
              <ThreadPrimitive.Messages>
                {({message})=>message.role==='user'?
                  <MessagePrimitive.Root className="userrow"><div className="userbubble"><MessagePrimitive.Parts/></div></MessagePrimitive.Root>:
                  <MessagePrimitive.Root className="assistantrow"><div className="assistantavatar"><Activity size={17}/></div><div className="assistantbody"><div className="assistanttext"><MessagePrimitive.Parts/></div>
                    <ToolCard ui={messages.find(m=>m.id===message.id)?.ui} onApproval={approval} onProject={onProject} token={token} project={project} mode={mode}/>
                  </div></MessagePrimitive.Root>}
              </ThreadPrimitive.Messages>
              {running&&<div className="statusline" aria-live="polite"><LoaderCircle size={16} className="spin"/>{status}</div>}
              {error&&<div className="statuserror" role="alert"><CircleAlert size={17}/>{error}<button onClick={()=>setError('')} aria-label="بستن خطا"><X size={14}/></button></div>}
              <ThreadPrimitive.ViewportFooter className="composerwrap">
                <ComposerPrimitive.Root className="composer">
                  <ComposerPrimitive.Input className="composerinput" placeholder="درخواستت رو بنویس، مثل «چرا سایتم خطای ۵۰۰ می‌ده؟»" aria-label="پیام کاربر" rows={2}/>
                  <div className="composerfooter"><span><ShieldCheck size={13}/> عملیات حساس با تأیید شما انجام می‌شود.</span><ComposerPrimitive.Send className="sendbutton" aria-label="ارسال پیام"><ArrowUp size={19}/></ComposerPrimitive.Send></div>
                </ComposerPrimitive.Root>
                <div className="footnote"><BookOpen size={12}/> {mode==='demo'?'داده‌ها و عملیات این محیط مصنوعی‌اند.':'اطلاعات واقعی فقط در محدوده دسترسی و سیاست مجاز خوانده می‌شوند.'} {engine && <span dir="ltr">· {engine}</span>}</div>
              </ThreadPrimitive.ViewportFooter>
            </ThreadPrimitive.Viewport>
          </ThreadPrimitive.Root>
        </div>
      </main>
    </div>
  </AssistantRuntimeProvider>;
}
