import { store } from './store.js';
const views=['home','map','observations','missions','drone','log'];
const labels={home:'概要',map:'森林マップ',observations:'観測結果',missions:'調査依頼',drone:'機体情報',log:'活動ログ'};
const e=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const date=value=>new Date(value).toLocaleString('ja-JP');
const badge=value=>'<span class="badge '+e(value.toLowerCase())+'">'+e(value)+'</span>';
const link=(target,text)=>'<a class="button" href="#'+e(target)+'">'+e(text)+'</a>';
const dl=rows=>'<dl>'+rows.map(([a,b])=>'<div><dt>'+e(a)+'</dt><dd>'+e(b)+'</dd></div>').join('')+'</dl>';
let filter='ALL',busy=false;
const content=document.querySelector('main');
const notice=document.querySelector('#notice');
let timer;
function notify(message){notice.textContent=message;clearTimeout(timer);timer=setTimeout(()=>notice.textContent='',7000);}
function observationCard(o){return '<article class="card"><div class="row">'+badge(o.status)+'<span class="muted">'+e(o.area_id)+'</span></div><h3>'+e(o.label)+'</h3><p class="muted">'+e(o.id)+' · '+e(date(o.captured_at))+'</p><div class="confidence"><strong>'+Math.round(o.confidence*100)+'%</strong> AI Confidence</div>'+link('observations/'+o.id,'観測詳細を見る →')+'</article>';}
function map(data){return '<div class="forest-map" aria-label="森林区画の模式図">'+data.areas.map(a=>'<div class="area" style="left:'+a.bounds.x+'%;top:'+a.bounds.y+'%;width:'+a.bounds.width+'%;height:'+a.bounds.height+'%"><span>'+e(a.id)+'<small>'+e(a.name)+'</small></span></div>').join('')+data.observations.map(o=>'<a class="marker '+e(o.status.toLowerCase())+'" style="left:'+o.position.x+'%;top:'+o.position.y+'%" href="#observations/'+e(o.id)+'" aria-label="'+e(o.id+' '+o.label)+'">'+(o.status==='NORMAL'?'●':'!')+'</a>').join('')+data.drones.map(d=>'<a class="marker drone" style="left:'+d.position.x+'%;top:'+d.position.y+'%" href="#drone" aria-label="'+e(d.id)+'">✦</a>').join('')+'<span class="north">↑ N</span><span class="map-caption">模式図 · 座標はデモ用</span></div><p class="legend">● 正常　<span>! 要確認 / 異常</span>　✦ 機体　· 地点を選択して詳細へ</p>';}
function render(){
 const {data,persistent}=store.getSnapshot();
 const [raw,id]=location.hash.slice(1).split('/');const view=views.includes(raw)?raw:'home';
 document.querySelector('nav').innerHTML=views.map(v=>'<a href="#'+v+'" '+(v===view?'aria-current="page"':'')+'><span>'+v.toUpperCase()+'</span>'+labels[v]+'</a>').join('');
 let html='<div class="page-heading"><p class="eyebrow">FOREST / '+view.toUpperCase()+'</p><h1>'+labels[view]+'</h1><p class="muted">森林の変化を見つけ、次の観測につなげる。</p></div>';
 if(!persistent) html+='<p class="warning">ブラウザーに保存できないため、再読み込みで操作内容がリセットされます。</p>';
 if(view==='home'){
 html+='<section class="hero"><p class="eyebrow">AUTONOMOUS FOREST CONSERVATION</p><h2>森林を、<br>見守り続ける。</h2><p>観測から理解へ。そして、もう一度現場へ。</p>'+link('observations/OBS-0184','要確認の観測を見る ↗')+'</section><div class="stats">'+[['調査区画',data.areas.length],['要確認・異常',data.observations.filter(o=>o.status!=='NORMAL').length],['再観測の依頼',data.missions.filter(m=>m.status==='REQUESTED').length],['機体バッテリー',data.drones[0].battery_pct+'%']].map(([label,n])=>'<div class="card"><span class="muted">'+label+'</span><strong>'+n+'</strong></div>').join('')+'</div><div class="section-title"><h2>最新の観測</h2>'+link('observations','すべてを見る')+'</div><div class="grid">'+data.observations.slice(0,2).map(observationCard).join('')+'</div>';
 }
 if(view==='map') html+=map(data)+'<div class="grid">'+data.areas.map(a=>'<article class="card"><h3>'+e(a.id)+' / '+e(a.name)+'</h3>'+badge(a.health)+'</article>').join('')+'</div>';
 if(view==='observations'){
 const o=data.observations.find(o=>o.id===id);
 if(id && !o) html+='<p>観測が見つかりません。</p>'+link('observations','一覧に戻る');
 else if(o){const existing=data.missions.find(m=>m.type==='REOBSERVE'&&m.target.observation_id===o.id&&['REQUESTED','ACCEPTED','RUNNING'].includes(m.status));
 html+=link('observations','← 観測一覧')+'<div class="detail"><figure><img src="'+e(o.image_url)+'" alt="樹冠を模したデモ画像。実際の観測写真ではありません。"><figcaption>シミュレーション画像 / 実際の観測写真ではありません</figcaption></figure><article class="card">'+badge(o.status)+'<h2>'+e(o.label)+'</h2><p>'+e(o.note)+'</p><div class="confidence"><strong>'+Math.round(o.confidence*100)+'%</strong> AI Confidence</div>'+dl([['Observation',o.id],['Area',o.area_id],['Drone',o.drone_id],['観測時刻',date(o.captured_at)],['緯度 / 経度',o.position.lat+' / '+o.position.lng]])+'<p class="muted">再観測条件：高度上限20m / ジオフェンス必須</p><button class="primary" data-reobserve="'+e(o.id)+'" '+(busy||existing?'disabled':'')+'>'+(existing?'再観測依頼済み · '+e(existing.id):busy?'作成中…':'再観測を依頼する')+'</button>'+link('missions','Mission一覧を見る')+'</article></div>';}
 else html+='<label class="filter">状態 <select id="filter">'+['ALL','NORMAL','REVIEW','ANOMALY'].map(s=>'<option '+(s===filter?'selected':'')+'>'+s+'</option>').join('')+'</select></label><div class="grid">'+data.observations.filter(o=>filter==='ALL'||o.status===filter).map(observationCard).join('')+'</div>';
 }
 if(view==='missions') html+='<p class="muted">REQUESTEDは依頼の作成状態です。実機は自動で飛行しません。</p><div class="grid">'+[...data.missions].reverse().map(m=>'<article class="card"><div class="row"><h2>'+e(m.id)+'</h2>'+badge(m.status)+'</div><h3>'+e(m.type)+'</h3>'+dl([['区域',m.target.area_id],['対象観測',m.target.observation_id||'区域巡回'],['理由',m.reason],['高度上限',m.constraints.max_altitude_m+' m'],['ジオフェンス',m.constraints.geofence_required?'必須':'任意'],['作成時刻',date(m.created_at)]])+(m.target.observation_id?link('observations/'+m.target.observation_id,'対象の観測を見る'):'')+'</article>').join('')+'</div>';
 if(view==='drone') html+='<div class="grid">'+data.drones.map(d=>'<article class="card"><p class="eyebrow">SURVEY VEHICLE</p><h2>'+e(d.id)+'</h2>'+badge(d.status)+'<div class="battery"><span style="width:'+d.battery_pct+'%"></span></div>'+dl([['バッテリー',d.battery_pct+'%'],['GPS',d.gps],['Jetson',d.jetson],['高度',d.altitude_m+' m'],['緯度 / 経度',d.position.lat+' / '+d.position.lng],['最終受信',date(d.last_seen_at)]])+'<p class="muted">サンプルの機体テレメトリーです。</p></article>').join('')+'</div>';
 if(view==='log') html+='<div class="timeline">'+data.logs.map(l=>'<article class="card"><p class="eyebrow">'+e(l.event)+'</p><h3>'+e(l.message)+'</h3><p class="muted">'+e(date(l.time))+' · '+e(l.id)+'</p>'+(l.mission_id?link('missions',l.mission_id+'を確認'):'')+'</article>').join('')+'</div>';
 content.innerHTML=html;
}
content.addEventListener('change',event=>{if(event.target.id==='filter'){filter=event.target.value;render();}});
content.addEventListener('click',async event=>{const button=event.target.closest('[data-reobserve]');if(!button||busy)return;busy=true;render();try{const result=await store.requestReobserve(button.dataset.reobserve);notify(result.duplicate?'既存の依頼 '+result.mission.id+' を確認してください。':result.mission.id+' を作成し、LOGに記録しました。');}catch(error){notify(error.message);}finally{busy=false;render();document.querySelector('[data-reobserve]')?.focus();}});
window.addEventListener('hashchange',()=>{render();content.focus();window.scrollTo(0,0);});
store.subscribe(render);
try{await store.init();render();}catch{content.textContent='読み込みに失敗しました。ページを再読み込みしてください。';}