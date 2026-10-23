'use strict';
const $ = s => document.querySelector(s);
const esc = x => String(x ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt = (n, d=2) => Number.isFinite(+n) && n !== null && n !== undefined ? (+n).toLocaleString('en-US', {minimumFractionDigits:d, maximumFractionDigits:d}) : '—';
const pct = (n,d=2) => Number.isFinite(n)?fmt(n,d)+'%':'—';
const signed = (n,d=2) => (n > 0 ? '+' : '')+fmt(n,d);
const MODES = ['origin','full','s0','s1'];
const COLORS = {origin:'#8793a5',full:'#d99338',s0:'#20a59a',s1:'#6171ed'};
const DESCS = {origin:'无缓存',full:'全量失效',s0:'扫描 Base',s1:'选择性失效'};
const CASES = {'deep-static':'深层 select · 静态调用','wide-static':'多调用点 · 静态调用','leaf-static':'叶子类型 · 静态调用','tce-cha':'类型检查消除 + CHA','virtual-cfg':'虚调用 · CFG 修改','cff-cache-reuse':'常量字段折叠 · 缓存复用'};
const TABS = {overview:'实验总览',stacks:'调用栈探索',compare:'策略对比',source:'源码与汇编',quality:'采样质量与原始资料',method:'测试说明与伪代码'};
const GROUPS = {
  'javatype/query_lvi':['JavaType / LVI','#e58566'],
  'javatype/invalidation':['失效处理','#c990c5'],
  'javatype/lifecycle':['缓存生命周期','#b8a3de'],
  'javatype/query_callback':['JavaType / 回调','#efb367'],
  'javatype/query_allocation':['JavaType / 分配','#bead82'],
  'javatype/query_container':['JavaType / 容器','#8badd4'],
  'javatype/query_base':['JavaType / Base','#737ee0'],
  'javatype/query_facts_other':['JavaType / Facts','#8e9cf0'],
  'javatype/query_type_operations':['JavaType / 类型运算','#a6aee4'],
  'javatype/query_other':['JavaType / 其他','#bec4eb'],
  'external/parse':['IR 解析','#64b6ad'],
  'external/callback':['外部回调','#e9ce92'],
  'external/lvi':['外部 LVI','#deb5a5'],
  'external/dt':['外部支配树','#69a2c2'],
  'external/allocation':['外部分配','#bbc8cd'],
  'external/unknown':['外部未知','#cad0dc'],
  'external/other':['外部其他','#e3e7ee']};
let state = {dataset:'',case:'deep-static',mode:'s1',run:'all',tab:'overview',scope:'all',search:'',baseline:'origin',candidate:'s1'};
const hash = new URLSearchParams(location.hash.slice(1));
for (const key of ['dataset','case','mode','run','tab']) if (hash.has(key)) state[key]=hash.get(key);
if (![...MODES,'cold','cached'].includes(state.mode)) state.mode='s1';
if (!TABS[state.tab]) state.tab='overview';
if (!['all','run-00','run-01','run-02'].includes(state.run)) state.run='all';
let data, datasets=[], revision=0, datasetRevision=0, sourceRevision=0, loadedProfile=null, activeTree=null, selectedFrame=null, hitRects=[];
const profileCache = new Map();
const staticBase = document.documentElement.dataset.base || '';
const slug = x => String(x).replace(/[^A-Za-z0-9_.-]/g,'-');
const pathURL = p => p.split('/').map(encodeURIComponent).join('/');
const apiPath = (kind,extra={}) => {
 const entry=datasets.find(d=>d.id===state.dataset)||{};
 if(!staticBase){
   const endpoint={profiles:'profile',artifacts:'raw',records:'record'}[kind]||kind;
   return '/api/'+endpoint+'?'+new URLSearchParams({dataset:state.dataset,...extra});
 }
 if(kind==='datasets')return `${staticBase}/api/datasets.json`;
 if(kind==='overview'||kind==='status')return `${staticBase}/api/${entry[kind+'_url']||kind+'.json'}`;
 if(kind==='profiles'||kind==='speedscope')return `${staticBase}/api/${kind}/${slug(`${extra.case}--${extra.mode}--${extra.run}`)}${kind==='profiles'?'.json':'.speedscope.json'}`;
 return `${staticBase}/api/${kind}/${pathURL((kind==='artifacts'?(entry.artifact_prefix||''):'')+extra.file)}`;
};
const api = (kind,extra={}) => apiPath(kind,extra)+(staticBase?'?v=all-nine-20261023':'');
function recordURL(run,kind){
 if(!staticBase)return api('records',{case:state.case,mode:state.mode,run,kind});
 const archive=loadedProfile.archive_names?.[run] || (run.startsWith('diag:')?'diagnostics/quality/'+run.slice(5)+'/stacks.txt':`${state.case==='cff-cache-reuse'?'l2/':''}profiles/${state.case}/${state.mode}/${run}/stacks.txt`);
 return api('records',{file:archive.replaceAll('/','__')+'__'+kind});
}
function syncHash(){location.replace('#'+new URLSearchParams(Object.fromEntries(['dataset','case','mode','run','tab'].map(k=>[k,state[k]]))));}
function runs(){return data.attribution.profiles.filter(p=>p.case===state.case && p.mode===state.mode && (state.run==='all'||p.run===state.run));}
function summary(mode=state.mode){return data.attribution.summary.find(p=>p.case===state.case&&p.mode===mode);}
function median(values){const a=values.slice().sort((a,b)=>a-b);return a.length?a.length%2?a[a.length>>1]:(a[a.length/2-1]+a[a.length/2])/2:0;}
function stat(mode){return data.stat[state.case]?.[mode];}
function base(mode){return data.baseline[state.case]?.[mode];}
function modeLabel(mode){return `<span class="dot" style="background:${COLORS[mode]}"></span>${mode.toUpperCase()}`;}
function card(title,subtitle,body){return `<section class="card"><h2>${title}</h2>${subtitle?`<p>${subtitle}</p>`:''}${body}</section>`;}
function kpi(label,value,unit,detail){return `<section class="card kpi"><div class="label">${label}</div><div class="value">${value}<span class="unit">${unit}</span></div><div class="detail">${detail}</div></section>`;}
function table(head,rows){return `<div class="table-wrap"><table><thead><tr>${head.map((x,i)=>`<th${i?' class="num"':''}>${x}</th>`).join('')}</tr></thead><tbody>${rows.join('')}</tbody></table></div>`;}
function row(cells,cls=''){return `<tr class="${cls}">${cells.map((x,i)=>`<td${i?' class="num"':''}>${x}</td>`).join('')}</tr>`;}
function selectedGroups(mode=state.mode){
 const rows=data.partitions.filter(p=>p.case===state.case&&p.mode===mode&&(state.run==='all'||p.run===state.run));
 const totals={};const byRun={};
 for(const r of rows){totals[r.category]=(totals[r.category]||0)+(+r.period_sum);(byRun[r.run]??={})[r.category]=+r.period_sum;}
 const n=Object.keys(byRun).length||1,total=Object.values(totals).reduce((a,b)=>a+b,0);
 return Object.fromEntries(Object.entries(totals).map(([k,w])=>[k,{weight:w,mean:w/n,pct:100*w/total}]));
}
function renderOverview(){
 const b=base(state.mode),s=summary(),r=runs();
 const jt=median(r.map(p=>p.jt_pct)),lvi=median(r.map(p=>p.jt_lvi_pct));
 const delta=100*(b.user_s.median/base('origin').user_s.median-1);
 const max=Math.max(...MODES.map(m=>base(m).user_s.median));
 const bars=MODES.map(m=>`<div class="chart-row"><span>${modeLabel(m)}</span><div class="bar-track"><div class="bar-fill" style="width:${base(m).user_s.median/max*100}%;background:${COLORS[m]}"></div></div><span class="bar-value">${fmt(base(m).user_s.median,4)} s</span></div>`).join('');
 const partition=MODES.map(m=>{const groups=selectedGroups(m);return `<div class="chart-row"><span>${modeLabel(m)}</span><div class="bar-track">${Object.entries(GROUPS).filter(([k])=>groups[k]).map(([k,[name,color]])=>`<div style="width:${groups[k].pct}%;background:${color}" title="${name}: ${pct(groups[k].pct)}"></div>`).join('')}</div><span class="bar-value">100%</span></div>`;}).join('');
 const metrics=MODES.map(m=>{const b=base(m),s=stat(m),q=data.quality.scheduling.find(q=>q.case===state.case&&q.mode===m);return row([modeLabel(m),fmt(b.user_s.median,4),fmt(b.wall_s.median,4),fmt(s?.cpu_atom?.['cpu_atom/cycles/u']?.median/1e9,3),fmt(s?.ipc?.median,3),fmt(q?.max_rss_kb_median/1024,1)],m===state.mode?'selected-row':'');});
 const groups=selectedGroups();
 const consumers=data.consumers.filter(p=>p.case===state.case&&p.mode===state.mode&&(state.run==='all'||p.run===state.run));
 const who={};for(const c of consumers)who[c.consumer]=(who[c.consumer]||0)+(+c.period_sum);
 const totalWho=Object.values(who).reduce((a,b)=>a+b,0);
 return `<div class="kpis">${kpi('USER CPU · 十轮中位数',fmt(b.user_s.median,4),'s',`相对 ORIGIN ${signed(delta)}% · ${DESCS[state.mode]}`)}${kpi('JAVATYPE · 周期占比中位数',fmt(jt),'%',`${r.length} 份采样 · 包含查询、失效及生命周期`)}${kpi('JAVATYPE → LVI · 进程占比',fmt(lvi),'%','包含调用栈中位于 JavaType 下的 LVI')}${kpi('有效采样 · 当前范围',fmt(r.reduce((n,p)=>n+p.samples,0),0),'',`JavaType 样本 ${fmt(r.reduce((n,p)=>n+p.jt_samples,0),0)}`)}</div>
 <div class="grid2 equal">${card('四种策略，端到端开销','user CPU · 10 轮中位数 · 越短越好',bars)}${card('周期花在哪里','互斥分类 · 当前采样范围合并，按 period 加权',partition+`<div class="legend">${Object.values(GROUPS).map(([n,c])=>`<span><i style="background:${c}"></i>${n}</span>`).join('')}</div>`)}</div>
 ${card('运行指标','计时：10 轮中位数；硬件计数与校正 RSS：独立 3 轮中位数。采样范围选择不改变这些独立测量值。',table(['策略','user / s','wall / s','cycles / 10⁹','IPC','RSS / MiB'],metrics))}
 <div class="grid2 equal">${card('JavaType 的成本构成','当前范围；总进程周期为分母',table(['互斥分类','占比','平均 cycles / run'],Object.entries(groups).filter(([k])=>k.startsWith('javatype/')).sort((a,b)=>b[1].weight-a[1].weight).map(([k,g])=>row([GROUPS[k]?.[0]||esc(k),pct(g.pct),fmt(g.mean/1e6,2)+' M']))))}${card('谁在消费 JavaType','按 JavaType 周期加权；截断调用栈可能无法恢复消费者',table(['消费者','JavaType 内占比'],Object.entries(who).sort((a,b)=>b[1]-a[1]).map(([k,v])=>row([esc(k),pct(v/totalWho*100)]))))}</div>
 <div class="note blue">范围是 LLVM replay。主采样的 8 KiB 调用栈存在截断；未知 libc 叶子保留为 unknown。计时、采样占比和硬件计数来自独立运行，不把占比下降直接解释为加速。</div>`;
}
function renderCompare(){
 const a=state.baseline,b=state.candidate,ga=selectedGroups(a),gb=selectedGroups(b);
 const ba=base(a).user_s,bb=base(b).user_s;
 const categories=Object.keys(GROUPS).filter(k=>ga[k]||gb[k]);
 const body=categories.map(k=>{const x=ga[k]||{mean:0,pct:0},y=gb[k]||{mean:0,pct:0};return row([GROUPS[k][0],pct(x.pct),pct(y.pct),signed(y.pct-x.pct)+' pp',fmt(x.mean/1e6)+' M',fmt(y.mean/1e6)+' M',`<span class="${y.mean<x.mean?'good':'bad'}">${signed((y.mean-x.mean)/1e6)} M</span>`]);});
 const paired=data.paired[`${state.case}:s1_minus_${a}`];
 const ci=b==='s1'&&paired?paired.median_delta_bootstrap_95:null;
 return `<div class="compare-controls"><label>基准 <select id="compare-base">${MODES.map(m=>`<option value="${m}" ${m===a?'selected':''}>${m.toUpperCase()}</option>`).join('')}</select></label><span>→</span><label>候选 <select id="compare-candidate">${MODES.map(m=>`<option value="${m}" ${m===b?'selected':''}>${m.toUpperCase()}</option>`).join('')}</select></label></div>
 <div class="kpis">${kpi(`${a.toUpperCase()} · USER CPU`,fmt(ba.median,4),'s','十轮中位数')}${kpi(`${b.toUpperCase()} · USER CPU`,fmt(bb.median,4),'s','十轮中位数')}${kpi('中位数之差',signed(bb.median-ba.median,4),'s',`${signed(100*(bb.median/ba.median-1))}% · 非配对估计`)}${kpi('配对中位数差 · 95% CI',ci?fmt(ci.estimate,4):'—','s',ci?`[${fmt(ci.low_95,4)}, ${fmt(ci.high_95,4)}] · bootstrap`:'当前组合无保存的配对置信区间')}</div>
 ${card('绝对周期与占比一起看','每轮平均采样 cycles = 当前所选重复的 period 总和 / 重复数；不同策略不直接比较三轮之和与单轮之和。',table(['互斥分类',a.toUpperCase(),b.toUpperCase(),'占比变化',`${a.toUpperCase()} cycles/run`,`${b.toUpperCase()} cycles/run`,'周期变化'],body))}
 <div class="note">采样 cycles 是 event period 的加权估计，包含 perf record 扰动。pp 表示百分点；这些行互斥且可加，总览中的 JavaType → LVI 等 inclusive 指标不能再相加。S0 与 S1 更适合隔离 Base 失效策略差异；ORIGIN 与 FULL 同时涉及缓存引擎差异。</div>`;
}
function renderSource(){
 return `${card('保留的源码与 perf annotate','只展示实验时保存的代码片段与行号；不把当前工作区源码当作采样时源码。',`<div class="toolbar"><label>视图 <select id="source-kind"><option value="source">源码上下文</option><option value="annotate">汇编热点</option></select></label><select id="source-file" aria-label="源码文件">${data.sources.map((s,i)=>`<option value="${i}">${esc(s.path.split('/').slice(-2).join('/'))}</option>`).join('')}</select></div><div id="source-body"></div>`)}`;
}
async function showSource(){
 const token=++sourceRevision;
 const target=$('#source-body');if(!target)return;
 if($('#source-kind').value==='source'){
  const s=data.sources[+$('#source-file').value];
  target.innerHTML=`<div class="source-meta"><div class="path mono">${esc(s.path)}</div><p class="hash">SHA-256 ${esc(s.sha256)}</p></div>${s.snippets.map(x=>`<h3>行 ${x.first}–${x.last}</h3><pre class="code">${esc(x.text)}</pre>`).join('')}`;
 }else{
  const name=$('#source-file').value;
  target.innerHTML='<div class="empty">加载汇编记录…</div>';
  const resp=await fetch(api('artifacts',{file:'annotate/'+name+'.txt'}));
  const txt=await resp.text();if(target.isConnected&&token===sourceRevision)target.innerHTML=`<p>保存的 perf annotate 原文；源码可用性与符号归属以记录为准。</p><pre class="code">${esc(txt)}</pre>`;
 }
}
function renderQuality(){
 const q=data.quality,r=runs(),s=data.quality.scheduling.find(q=>q.case===state.case&&q.mode===state.mode);
 const selected=r.map(p=>row([esc(p.run),fmt(p.samples,0),fmt(p.jt_samples,0),pct(p.unknown_pct),pct(p.root_complete_pct),pct(p.full_entry_within_jt_pct)]));
 const checks=q.quality_checks.map(x=>row([esc(x.tag),fmt(x.samples,0),esc(x.frequency),fmt(x.stack_bytes/1024,0),pct(x.pct.jt),pct(x.pct.jt_lvi),pct(x.pct.root_complete)]));
 return `${card('采样完整性','77 份主采样与质量对照记录；只把已记录的质量指标解释为证据。',`<div class="quality-stats"><div><b>${fmt(q.lost_record_count,0)}</b><span>LOST RECORDS</span></div><div><b>${fmt(q.lost_sample_record_count,0)}</b><span>LOST SAMPLES</span></div><div><b>${fmt(q.throttle_record_count,0)}</b><span>THROTTLES</span></div><div><b>${q.native_stats_profiles}</b><span>PROFILES CHECKED</span></div></div>`+table(['重复','样本','JavaType 样本','未知叶子','到进程根完整','JavaType 查询边界可见'],selected))}
 <div class="note">零丢样不代表栈完整。主实验 8 KiB 栈可能截断，32 KiB 对照用于验证归属。小样本场景不适合细分热点排名；399 Hz 对照的额外开销约 5.15%，主实验保留 199 Hz。</div>
 ${card('频率与栈深对照','诊断记录为独立 S1 采样，不与主实验三份记录混合。',table(['对照','样本','Hz','栈 / KiB','JavaType','JavaType → LVI','进程根完整'],checks))}
 ${card('修正后的资源指标',`当前 ${state.mode.toUpperCase()} · 独立 ${s?.repeats||3} 次运行的中位数 · opt 子进程 wait4`,table(['指标','数值'],[row(['RSS',fmt(s?.max_rss_kb_median/1024,1)+' MiB']),row(['主动上下文切换',fmt(s?.voluntary_context_switches_median,0)]),row(['被动上下文切换',fmt(s?.involuntary_context_switches_median,0)])])+`<p>早期 baseline RSS 继承父进程高水位，不能使用。perf 的 :u context-switches / migrations 为零也不用于证明无调度或迁移。</p>`)}
 ${card('实验身份与原始资料','本站提供冻结实验的只读资料。原始 perf.data 留在测试服务器，站点保存逐样本栈和采样记录。',`<div class="hash">数据指纹 ${esc(data.fingerprint)}<br>HEAD ${esc(data.manifest.identity?.head)}<br>opt SHA-256 ${esc(data.manifest.identity?.opt_sha256)}<br>patch SHA-256 ${esc(data.manifest.identity?.source_patch_sha256)}</div><div class="artifact-list">${data.files.map(f=>`<a href="${api('artifacts',{file:f})}" target="_blank" rel="noopener">↗ ${esc(f)}</a>`).join('')}</div>`)}
 ${card('结构诊断','8 函数独立验证用例，包含 verification 额外开销；计数用于解释行为，计时不能用于性能排名。',`<details><summary>查看当前场景的四策略计数</summary><pre>${esc(JSON.stringify(data.structural.filter(x=>x.case===state.case),null,2))}</pre></details>`)}
 <div class="note blue">实验限制：L1 profile 策略顺序固定；baseline 十轮与 L2 采样已打乱顺序。当前数据不覆盖完整 JVM 流程、RecoverTypeInfo 和全部 pre-PEA 路径，也不满足两次独立会话的正式性能结论要求。</div>`;
}
function renderStacks(){
 const checks=data.quality.quality_checks.filter(c=>c.case===state.case);
 if(!checks.some(c=>'diag:'+c.tag===state.diagnostic))state.diagnostic='';
 return card('沿调用栈寻找成本','根在上方，叶子在下方。块宽代表 sampled cycles；点击放大并查看函数关系。递归栈保留原始顺序。',`<div class="toolbar"><input id="stack-search" type="search" placeholder="搜索函数或 native owner…" value="${esc(state.search)}" aria-label="搜索调用栈"><label>过滤 <select id="scope"><option value="all">整个 opt 进程</option><option value="jt">JavaType 相关样本</option><option value="lvi">JavaType → LVI</option><option value="invalid">失效处理</option><option value="unknown">未知叶子</option></select></label><button id="reset-zoom">重置缩放</button>${checks.length?`<label>记录 <select id="diagnostic"><option value="">主实验 · 使用上方策略与重复</option>${checks.map(c=>`<option value="diag:${esc(c.tag)}" ${state.diagnostic==='diag:'+c.tag?'selected':''}>S1 诊断 · ${esc(c.tag)}</option>`).join('')}</select></label>`:''}</div><p id="stack-stats"></p><div id="breadcrumbs"></div><div id="stack-loading" class="empty"><span class="spinner"></span>正在读取调用栈索引…</div><div class="graph-wrap"><canvas id="flame" aria-label="可缩放调用栈图"></canvas></div><p class="tiny muted">最多显示当前节点往下 80 层；点击底部节点可继续深入。横轴是周期权重，不是时间线。</p><div class="grid2"><div><div class="split-head"><h3>函数成本</h3><label class="tiny muted">排序 <select id="cost-sort"><option value="inclusive">Inclusive</option><option value="self">Self</option></select></label></div><p class="tiny">Inclusive 对同一帧的递归按每样本计一次；不同函数之间有重叠。点击名称查看关系。</p><div id="functions" class="table-scroll"></div></div><div><h3>调用关系</h3><div id="relations"><p>选择图中节点或函数。</p></div></div></div><details><summary>原始采样记录</summary><div id="record-links" class="artifact-list"></div></details>`);
}
function filteredSamples(){
 return loadedProfile.samples.filter(s=>state.scope==='all'||(state.scope==='jt'?s.flags.includes('jt'):state.scope==='lvi'?s.flags.includes('jt')&&s.flags.includes('lvi'):s.flags.includes(state.scope)));
}
function buildTree(samples){
 const root={id:-1,value:0,children:new Map(),parent:null};
 for(const s of samples){let node=root;node.value+=s.weight;for(const id of s.stack){if(!node.children.has(id))node.children.set(id,{id,value:0,children:new Map(),parent:node});node=node.children.get(id);node.value+=s.weight;}}
 return root;
}
function frameName(id){return id<0?'opt · 全部选中样本':loadedProfile.frames[id].name;}
function frameMatches(id){if(!state.search)return true;if(id<0)return false;const f=loadedProfile.frames[id];return (f.name+' '+f.native).toLowerCase().includes(state.search.toLowerCase());}
function frameColor(id){if(id<0)return '#e1e7f2';const f=loadedProfile.frames[id],s=f.name+' '+f.native;if(s.includes('[unknown]'))return '#c9cfd9';if(/LazyValueInfo|solveBlockValue|isNullEdge/.test(s))return '#e8a085';if(/invalidate|~JavaType/.test(s))return '#c6a0ce';if(/JavaType|factsAt|phiValueType/.test(s))return '#9b9fe5';if(/parse|LLParser|LLLexer/.test(s))return '#8fc5ba';if(/Dominator|DomTree/.test(s))return '#92bad4';let v=0;for(const c of f.name)v=(v*31+c.charCodeAt(0))|0;return `hsl(${205+Math.abs(v)%48} 43% ${76+Math.abs(v)%12}%)`;}
function drawFlame(){
 const canvas=$('#flame');if(!canvas||!activeTree)return;
 const width=Math.max(500,canvas.parentElement.clientWidth-2);
 const rects=[];let maxDepth=0;
 const visit=(node,x,w,depth)=>{if(w<.6||depth>=80)return;rects.push({node,x,w,y:depth*23});maxDepth=Math.max(maxDepth,depth);let offset=x;for(const child of [...node.children.values()].sort((a,b)=>b.value-a.value)){const cw=w*child.value/node.value;visit(child,offset,cw,depth+1);offset+=cw;}};
 visit(activeTree,0,width,0);const logicalHeight=(maxDepth+1)*23;
 const ratio=window.devicePixelRatio||1;canvas.width=width*ratio;canvas.height=logicalHeight*ratio;canvas.style.width=width+'px';canvas.style.height=logicalHeight+'px';const ctx=canvas.getContext('2d');ctx.scale(ratio,ratio);ctx.font='10px -apple-system, sans-serif';hitRects=rects;
 for(const r of rects){ctx.globalAlpha=state.search&&!frameMatches(r.node.id)?.27:1;ctx.fillStyle=frameColor(r.node.id);ctx.fillRect(r.x+.5,r.y+.5,Math.max(0,r.w-1),21);if(r.node.id===selectedFrame){ctx.strokeStyle='#4e5fe4';ctx.lineWidth=2;ctx.strokeRect(r.x+1,r.y+1,r.w-2,19);}if(r.w>30){ctx.save();ctx.beginPath();ctx.rect(r.x+4,r.y,r.w-8,22);ctx.clip();ctx.fillStyle='#263a51';ctx.fillText(frameName(r.node.id),r.x+5,r.y+14);ctx.restore();}}ctx.globalAlpha=1;
 const chain=[];for(let n=activeTree;n;n=n.parent)chain.unshift(n);
 $('#breadcrumbs').innerHTML=chain.map((n,i)=>`<button data-crumb="${i}" title="${esc(frameName(n.id))}">${esc(frameName(n.id))}</button>`).join('<span class="muted">›</span>');
 $('#breadcrumbs').onclick=e=>{const b=e.target.closest('[data-crumb]');if(b){activeTree=chain[+b.dataset.crumb];drawFlame();}};
}
function showCosts(){
 if(!loadedProfile)return;const samples=filteredSamples(),costs=new Map();
 for(const s of samples){for(const id of new Set(s.stack)){if(!costs.has(id))costs.set(id,{id,inclusive:0,self:0});costs.get(id).inclusive+=s.weight;}costs.get(s.stack.at(-1)).self+=s.weight;}
 const total=samples.reduce((a,s)=>a+s.weight,0),sort=$('#cost-sort')?.value||'inclusive';
 const list=[...costs.values()].filter(f=>frameMatches(f.id)).sort((a,b)=>b[sort]-a[sort]).slice(0,150);
 $('#functions').innerHTML=table(['函数','Inclusive','Self'],list.map(f=>row([`<div class="symbol" title="${esc(loadedProfile.frames[f.id].native||frameName(f.id))}"><button class="symbol-button" data-frame="${f.id}">${esc(frameName(f.id))}</button></div>`,pct(100*f.inclusive/total),pct(100*f.self/total)],f.id===selectedFrame?'selected-row':'')));
 $('#functions').onclick=e=>{const b=e.target.closest('[data-frame]');if(b){selectedFrame=+b.dataset.frame;showRelations();showCosts();drawFlame();}};
 const matching=samples.filter(s=>s.stack.some(frameMatches)).reduce((a,s)=>a+s.weight,0);
 $('#stack-stats').textContent=samples.length?`${fmt(samples.length,0)} 个样本 · ${fmt(total/1e9,3)} G cycles · 占全部进程 ${pct(100*total/loadedProfile.period_sum)}${state.search?' · 搜索命中周期 '+pct(100*matching/total):''} · 函数表显示前 150 项（按当前过滤范围计百分比）`:'当前过滤范围没有样本；请切换策略或过滤条件。';
}
function showRelations(){
 if(selectedFrame===null||selectedFrame<0){$('#relations').innerHTML='<p>选择图中节点或函数。</p>';return;}
 const callers=new Map(),callees=new Map();let selectedWeight=0;
 for(const s of filteredSamples()){
  const before=new Set(),after=new Set();let found=false;
  s.stack.forEach((id,i)=>{if(id===selectedFrame){found=true;if(i>0)before.add(s.stack[i-1]);if(i<s.stack.length-1)after.add(s.stack[i+1]);}});
  if(found)selectedWeight+=s.weight;
  for(const id of before)callers.set(id,(callers.get(id)||0)+s.weight);
  for(const id of after)callees.set(id,(callees.get(id)||0)+s.weight);
 }
 const f=loadedProfile.frames[selectedFrame];
 const list=(title,map)=>`<h3>${title}</h3>`+table(['直接相邻函数','含该关系的周期'],[...map].sort((a,b)=>b[1]-a[1]).slice(0,20).map(([id,w])=>row([`<div class="symbol"><button class="symbol-button" data-relation="${id}" title="${esc(frameName(id))}">${esc(frameName(id))}</button></div>`,pct(100*w/selectedWeight)])));
 $('#relations').innerHTML=`<div class="selection">${esc(f.name)}${f.inline?' [inlined]':''}</div><p class="hash">Native owner: ${esc(f.native||'未恢复')}<br>同名 inline 帧按 native owner 区分；owner 不是额外的调用层。</p>${list('调用者',callers)}${list('被调用者',callees)}<p class="tiny">分母是包含所选函数的周期。每条相邻关系按样本去重；递归可产生重叠，不能相加。</p>`;
 $('#relations').onclick=e=>{const b=e.target.closest('[data-relation]');if(b){selectedFrame=+b.dataset.relation;showRelations();showCosts();drawFlame();}};
}
function refreshStacks(reset=true){
 if(!loadedProfile)return;if(reset)activeTree=buildTree(filteredSamples());drawFlame();showCosts();showRelations();
}
async function loadStacks(token){
 const profileRun=state.diagnostic||state.run;
 const key=[state.dataset,state.case,state.mode,profileRun].join('/');
 while(token===revision){
  try{
   let profile=profileCache.get(key);
   if(!profile){const response=await fetch(api('profiles',{case:state.case,mode:state.mode,run:profileRun}));if(!response.ok)throw Error('读取失败');profile=await response.json();if(token!==revision)return;if(profileCache.size>=8)profileCache.delete(profileCache.keys().next().value);profileCache.set(key,profile);}
   if(token!==revision)return;loadedProfile=profile;selectedFrame=null;$('#stack-loading').remove();$('#scope').value=state.scope;
   refreshStacks();$('#record-links').innerHTML=profile.runs.map(r=>['run.json','record.stderr','native-self.txt','native-stats.txt','stacks.txt'].map(kind=>`<a target="_blank" rel="noopener" href="${recordURL(r.run,kind)}">${esc(r.run)} / ${kind}</a>`).join('')).join('');const canvas=$('#flame');
   const hit=e=>{const r=canvas.getBoundingClientRect();return hitRects.find(x=>e.clientX-r.left>=x.x&&e.clientX-r.left<x.x+x.w&&e.clientY-r.top>=x.y&&e.clientY-r.top<x.y+22);};
   canvas.onmousemove=e=>{const r=hit(e),tip=$('#tooltip');if(!r){tip.hidden=true;return;}const f=r.node.id>=0?loadedProfile.frames[r.node.id]:null;tip.textContent=`${frameName(r.node.id)}${f?.inline?' [inlined]':''}\n${fmt(r.node.value/1e6)} M cycles · 当前节点的 ${pct(100*r.node.value/activeTree.value)}\n${f?.native?'Native owner: '+f.native:''}`;tip.hidden=false;tip.style.left=Math.min(e.clientX+14,innerWidth-550)+'px';tip.style.top=Math.max(10,Math.min(e.clientY+14,innerHeight-tip.offsetHeight-12))+'px';};
   canvas.onmouseleave=()=>$('#tooltip').hidden=true;
   canvas.onclick=e=>{const r=hit(e);if(r){activeTree=r.node;selectedFrame=r.node.id;$('#tooltip').hidden=true;drawFlame();showCosts();showRelations();}};return;
  }catch(err){if(token===revision)$('#stack-loading').textContent='调用栈加载失败：'+err.message;return;}
 }
}
const isReuse=()=>data?.kind==='context-reuse';
function renderMethod(){
 const m=data.methodology[state.case];
 return card('要回答的问题','',`<p>${esc(m.question)}</p>`)+
 card('测试构造','',`<p>${esc(m.setup)}</p><pre class="pseudocode">${esc(m.pseudocode)}</pre>`)+
 card('测试特点与控制变量','',`<ul>${m.features.map(x=>`<li>${esc(x)}</li>`).join('')}</ul>`)+
 card('如何解读结果','',`<p>${esc(m.interpretation)}</p>`)+
 card('测量口径与边界','',`<p>${esc(isReuse()?data.protocol:'原始四策略分别是 ORIGIN（原实现）、FULL（缓存引擎+全量失效）、S0（扫描 Base 依赖）、S1（选择性失效）。FULL 不是每次查询清缓存。计时为独立十轮，硬件计数与主采样分别为独立三轮；所有指标来自 LLVM replay，不是 JVM 应用吞吐量。S0/S1 更适合隔离 Base 失效策略，ORIGIN/FULL 同时改变缓存引擎。详细构造及原始记录见“采样质量与原始资料”。')}</p>`);
}
function renderReplay(){
 const c=state.case,s=data.summary[c],d=data.diagnostics[c],modes=[s.baseline_mode,'cached'];
 const max=Math.max(s.baseline_user_median,s.cached_user_median);
 const bars=modes.map(m=>{const v=s[m==='cached'?'cached_user_median':'baseline_user_median'];return `<div class="chart-row"><span>${m.toUpperCase()}</span><div class="bar-track"><div class="bar-fill" style="width:${100*v/max}%;background:${m==='cached'?'#6171ed':'#d99338'}"></div></div><span>${fmt(v,6)} s</span></div>`;}).join('');
 const pairs=[0,1,2].map(r=>{const pair=data.timings.filter(t=>t.scenario===c&&t.round===r);const a=pair.find(t=>t.mode===s.baseline_mode),b=pair.find(t=>t.mode==='cached');return row([r+1,fmt(a.user_s,6),fmt(b.user_s,6),pct(100*(1-b.user_s/a.user_s),3),fmt(a.wall_s,6),fmt(b.wall_s,6)]);});
 const diag=modes.map(m=>row([m.toUpperCase(),d[m].queries,d[m].final_hits,d[m].final_misses,d[m].facts_hits,d[m].facts_misses,d[m].oracle_calls,d[m].fresh_reference_checked?'全部通过':'未通过']));
 return `<div class="kpis">${kpi('配对 CPU 降低率',fmt(s.paired_cpu_reduction_pct_median,2),'%','逐轮降低率的中位数 · 仅三轮')}${kpi('CACHED · USER CPU',fmt(s.cached_user_median,6),'s','4096 批 · 三轮中位数')}${kpi('CACHED · FINAL HIT',fmt(d.cached.final_hits,0),' / '+d.cached.queries,'独立单批诊断；不是计时进程计数')}${kpi('CACHED · ORACLE CALLS',fmt(d.cached.oracle_calls,0),'',`基准 ${d[s.baseline_mode].oracle_calls} · 不等于 LVI 求解次数`)}</div>`+
 card('这个测试验证什么','',`<p>${esc(data.scenarios[c].question)}</p><p>${esc(data.scenarios[c].interpretation)}</p><button data-tab="method">查看完整构造与伪代码 →</button>`)+
 card('基准与缓存模式','原生 user CPU；每进程 4096 批，fixture 构造在计时范围外。',bars)+
 card('三轮配对结果','降低率 = (基准 − cached) / 基准；正值代表 cached 更快。秒数是整批循环成本，不是单次查询延迟。',table(['轮次',s.baseline_mode.toUpperCase()+' user/s','CACHED user/s','CPU 降低','基准 wall/s','CACHED wall/s'],pairs))+
 card('缓存与正确性诊断','单独运行 1 批；逐次查询对照 fresh DT / AC / LVI / JavaTypeCache。计时运行关闭计数与参考检查。',table(['模式','查询数','Final hit','Final miss','Facts hit','Facts miss','Oracle calls','fresh 对照'],diag))+
 `<div class="note blue">${esc(data.protocol)}</div>`;
}
function renderReplayRaw(){
 return card('代码与二进制身份','',`<div class="hash">branch: ${esc(data.source.branch)}<br>commit: <a href="https://github.com/Atm2086/jeandle-llvm/commit/${encodeURIComponent(data.source.commit)}" target="_blank" rel="noopener">${esc(data.source.commit)}</a><br>cache-design base: ${esc(data.source.parent)}<br>binary SHA-256: ${esc(data.identity.sha256)}<br>production LVI matches cache-design: ${esc(data.source.production_lvi_matches_cache_design_base)}<br>dataset SHA-256: ${esc(data.fingerprint)}</div>`)+
 card('验证与回放参数','',`<p>JavaType 单元测试 47/47；六组 lit 96/96。CPU ${data.identity.cpu}，seed ${data.identity.seed}，3 轮 × 3 场景 × 2 模式 = 18 个计时进程，每进程 ${data.identity.batches} 批。</p><p>本数据集没有 perf 采样栈、硬件 cycles 或 IPC；它与原四策略实验独立。</p>`)+
 card('原始资料','identity、逐轮计时、单批命中诊断、摘要、测试补丁和验证日志均可查阅。',`<div class="artifact-list">${data.files.map(f=>`<a href="${api('artifacts',{file:f})}" target="_blank" rel="noopener">↗ ${esc(f)}</a>`).join('')}</div>`);
}
function renderCaseNavigation(){
 const names={...CASES,final:'同键 Final 复用',prefix:'不同 BB 的路径前缀复用',mutation:'真实修改与选择性失效'};
 $('#cases').innerHTML=datasets.map(d=>`<div class="case-group-label">${d.kind==='context-reuse'?'新增 · 缓存复用（3）':'原有 · 性能剖析（6）'}</div>${d.cases.map(c=>`<button data-case="${esc(c)}" data-dataset-id="${esc(d.id)}" class="${d.id===state.dataset&&state.case===c?'active':''}">${esc(c)}<small>${esc(names[c]||'')}</small></button>`).join('')}`).join('');
 $('#case-count').textContent=datasets.reduce((n,d)=>n+d.cases.length,0);
}
function renderReuse(){
 const cases=Object.keys(data.scenarios),tabs={overview:'回放结果',method:'测试说明与伪代码',quality:'原始数据与验证'};
 if(!cases.includes(state.case))state.case=cases[0];
 if(!tabs[state.tab])state.tab='overview';
 syncHash();$('#title').textContent=state.case;
 $('#subtitle').textContent=data.scenarios[state.case].question;
 $('#modes').innerHTML='<span>独立 API 回放 · 基准与 CACHED 并列展示</span>';
 renderCaseNavigation();
 $('#tabs').innerHTML=Object.entries(tabs).map(([k,v])=>`<button data-tab="${k}" class="${k===state.tab?'active':''}">${v}</button>`).join('');
 $('#content').innerHTML=({overview:renderReplay,method:renderMethod,quality:renderReplayRaw})[state.tab]();
}
function render(){
 if(!data)return;const token=++revision;loadedProfile=null;activeTree=null;$('#tooltip').hidden=true;syncHash();
 $('#run').closest('label').hidden=isReuse();$('#export').hidden=isReuse();
 document.querySelector('footer').textContent=isReuse()?'CPU 16 · 原生 API 回放 · 三轮配对 · 计时与诊断分离':'CPU 16 · cpu_atom/cycles/u · event period 加权 · LLVM replay 范围';
 if(isReuse()){renderReuse();return;}
 if(!MODES.includes(state.mode))state.mode='s1';
 if(!data.baseline[state.case])state.case=Object.keys(data.baseline)[0];
 syncHash();$('#title').textContent=state.case;const c={...data.manifest.cases,...data.manifest.l2}[state.case]||{};
 $('#subtitle').textContent=`${CASES[state.case]||state.case} · ${fmt(c.functions,0)} functions · ${c.passes||''}`;
 $('#modes').innerHTML=MODES.map(m=>`<button data-mode="${m}" class="${m===state.mode?'active':''}" title="${DESCS[m]}">${modeLabel(m)}</button>`).join('');
 $('#tabs').innerHTML=Object.entries(TABS).map(([k,v])=>`<button data-tab="${k}" class="${k===state.tab?'active':''}">${v}</button>`).join('');
 renderCaseNavigation();
 $('#run').value=state.run;
 const content=$('#content');content.innerHTML=({overview:renderOverview,compare:renderCompare,source:renderSource,quality:renderQuality,stacks:renderStacks,method:renderMethod})[state.tab]();
 if(state.tab==='source')showSource();if(state.tab==='stacks')loadStacks(token);
}
async function changeDataset(id){
 const token=++datasetRevision;++revision;state.dataset=id;$('#content').innerHTML='<div class="empty">正在读取汇总…</div>';
 const response=await fetch(api('overview'));if(!response.ok)throw Error('读取数据失败');const next=await response.json();if(token!==datasetRevision)return;data=next;
 render();pollStatus();
}
let statusTimer;
async function pollStatus(){
 clearTimeout(statusTimer);try{const response=await fetch(api('status')),s=await response.json();$('#index-status').textContent=s.state==='ready'?`静态数据已就绪 · ${s.completed} 份`:`数据状态异常：${esc(s.errors?.join('; ') || s.state)}`;}catch(e){$('#index-status').textContent='数据连接中断';}
}
document.addEventListener('click',e=>{
 const b=e.target.closest('button');if(!b)return;
 if(b.dataset.mode){state.mode=b.dataset.mode;state.diagnostic='';render();}else if(b.dataset.case){state.case=b.dataset.case;state.diagnostic='';if(b.dataset.datasetId&&b.dataset.datasetId!==state.dataset){$('#dataset').value=b.dataset.datasetId;changeDataset(b.dataset.datasetId).catch(showError);}else render();}else if(b.dataset.tab){state.tab=b.dataset.tab;render();}
 if(b.id==='reset-zoom')refreshStacks();
 if(b.id==='export')window.open(api('speedscope',{case:state.case,mode:state.mode,run:state.tab==='stacks'&&state.diagnostic?state.diagnostic:state.run}),'_blank','noopener');
});
document.addEventListener('change',e=>{
 if(e.target.id==='run'){state.run=e.target.value;render();}
 if(e.target.id==='dataset')changeDataset(e.target.value).catch(showError);
 if(e.target.id==='scope'){state.scope=e.target.value;refreshStacks();}
 if(e.target.id==='diagnostic'){state.diagnostic=e.target.value;if(state.diagnostic)state.mode='s1';render();}
 if(e.target.id==='cost-sort')showCosts();
 if(e.target.id==='compare-base'){state.baseline=e.target.value;render();}
 if(e.target.id==='compare-candidate'){state.candidate=e.target.value;render();}
 if(e.target.id==='source-kind'){
  $('#source-file').innerHTML=e.target.value==='source'?data.sources.map((s,i)=>`<option value="${i}">${esc(s.path.split('/').slice(-2).join('/'))}</option>`).join(''):'<option value="poison">isGuaranteedNotToBePoison</option><option value="lvi-select">LazyValueInfo · Select</option><option value="invalidate">JavaTypeCache · invalidate</option>';showSource();
 }
 if(e.target.id==='source-file')showSource();
});
document.addEventListener('input',e=>{if(e.target.id==='stack-search'){state.search=e.target.value;if(loadedProfile){drawFlame();showCosts();}}});
window.addEventListener('resize',()=>{if(state.tab==='stacks')drawFlame();});
function showError(error){$('#content').innerHTML=`<div class="empty">加载失败：${esc(error.message)}</div>`;}
async function init(){
 const response=await fetch(api('datasets'));datasets=await response.json();if(!datasets.length)throw Error('未发现数据集');
 if(!datasets.some(d=>d.id===state.dataset))state.dataset=datasets[0].id;
 $('#dataset').innerHTML=datasets.map(d=>`<option value="${esc(d.id)}" ${d.id===state.dataset?'selected':''}>${esc(d.label||d.id)}</option>`).join('');
 await changeDataset(state.dataset);
}
init().catch(showError);
