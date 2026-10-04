import { store } from './store.js';
import { lookupWeather } from './weather.js';
import { observationHistory, previousObservation, latestPerSite } from './observation-history.js';
const views=['home','map','observations','missions','drone','log'];
const labels={home:'ホーム',map:'森林マップ',observations:'観測結果',missions:'調査依頼',drone:'機体情報',log:'活動ログ'};
const e=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const date=value=>new Date(value).toLocaleString('ja-JP');
const badge=value=>'<span class="badge '+e(value.toLowerCase())+'">'+e(value)+'</span>';
const link=(target,text)=>'<a class="button" href="#'+e(target)+'">'+e(text)+'</a>';
const dl=rows=>'<dl>'+rows.map(([a,b])=>'<div><dt>'+e(a)+'</dt><dd>'+e(b)+'</dd></div>').join('')+'</dl>';
let filter='ALL',busy=false;
let postal='',weather=null,weatherLoading=false,weatherError='',selectedArea='';
let savedPostal='',settingWarning='',weatherRequest=0;
try {const saved=localStorage.getItem('forest.postal.v1')||'';if(/^\d{7}$/.test(saved)){postal=saved;savedPostal=saved;}} catch {}
function regionControls(){
 if(savedPostal)return '<div class="saved-region"><div><span class="region-label">保存した地域</span><strong>〒'+e(savedPostal.slice(0,3)+'-'+savedPostal.slice(3))+'</strong><p class="muted">次回もこの地域を自動表示します。</p></div><div class="region-actions"><button type="button" id="weather-refresh" '+(weatherLoading?'disabled':'')+'>気象を更新</button><button type="button" id="region-delete">地域設定を削除</button></div></div>';
 return '<form id="weather-form"><label for="postal">郵便番号</label><div class="postal-row"><input id="postal" name="postal" inputmode="numeric" autocomplete="postal-code" maxlength="9" placeholder="例：100-0001" value="'+e(postal)+'" required><button type="submit" '+(weatherLoading?'disabled':'')+'>'+(weatherLoading?'取得中…':'地域を保存')+'</button></div><p class="muted">一度保存すると、削除するまでこのブラウザーで覚えます。</p></form>';
}
function weatherPanel(){
 const w=weather,c=w?.current;
 return '<section class="weather-panel '+(w?w.appearance.theme:'unconfigured')+'" aria-labelledby="weather-title"><div class="weather-art" aria-hidden="true">'+(w?w.appearance.icon:'◌')+'</div><div class="weather-content"><p class="eyebrow">LOCAL WEATHER</p><h2 id="weather-title">地域の気象情報</h2>'+regionControls()+''+(settingWarning?'<p class="warning" role="status">'+e(settingWarning)+'</p>':'')+'<p class="weather-status" role="status">'+e(weatherError||(weatherLoading?'地域の気象情報を取得しています。':w?'〒'+w.postal.slice(0,3)+'-'+w.postal.slice(3)+' · '+w.region:'郵便番号を設定して、地域の天気を表示します。'))+'</p>'+(w?'<div class="weather-reading"><strong>'+e(c.temperature_2m)+'<small>°C</small></strong><span>'+e(w.appearance.label)+'</span></div><div class="weather-metrics">'+[['風速',c.wind_speed_10m+' m/s'],['突風',c.wind_gusts_10m+' m/s'],['降水量',c.precipitation+' mm'],['湿度',c.relative_humidity_2m+'%']].map(([l,v])=>'<div><span>'+l+'</span><strong>'+e(v)+'</strong></div>').join('')+'</div><p class="weather-source">'+e(c.time.replace('T',' '))+' JST · 市区町村付近のモデル推定値<br>気象：<a href="https://open-meteo.com/" target="_blank" rel="noopener">Open-Meteo</a> · 住所：<a href="https://zipcloud.ibsnet.co.jp/" target="_blank" rel="noopener">zipcloud</a> · 位置：<a href="https://maps.gsi.go.jp/" target="_blank" rel="noopener">国土地理院</a></p>':'')+'</div></section>';
}
async function updateWeather(input){
 if(weatherLoading)return;
 const request=++weatherRequest;
 postal=input;weatherLoading=true;weatherError='';weather=null;render();
 try{
 const result=await lookupWeather(input);
 if(request!==weatherRequest)return;
 weather=result;postal=weather.postal;
 if(!savedPostal){
 try{localStorage.setItem('forest.postal.v1',postal);savedPostal=postal;settingWarning='';}
 catch{settingWarning='ブラウザーに保存できません。保存を許可すると、次回から自動表示できます。';}
 }
 }
 catch(error){if(request!==weatherRequest)return;weatherError=error.name==='AbortError'?'接続がタイムアウトしました。再度お試しください。':error instanceof TypeError?'気象サービスに接続できません。通信環境を確認して再度お試しください。':error.message;}
 finally{if(request===weatherRequest){weatherLoading=false;render();(document.querySelector('#weather-refresh')||document.querySelector('#postal'))?.focus();}}
}
function deleteRegion(){
 try{localStorage.removeItem('forest.postal.v1');}
 catch{settingWarning='地域設定を削除できませんでした。ブラウザーの保存設定を確認してください。';render();return;}
 ++weatherRequest;postal='';savedPostal='';weather=null;weatherLoading=false;weatherError='';settingWarning='';render();document.querySelector('#postal')?.focus();notify('保存した地域を削除しました。');
}
const content=document.querySelector('main');
const notice=document.querySelector('#notice');
let timer;
function notify(message){notice.textContent=message;clearTimeout(timer);timer=setTimeout(()=>notice.textContent='',7000);}
function observationCard(o){return '<article class="card"><div class="row">'+badge(o.status)+'<span class="muted">'+e(o.area_id)+'</span></div><h3>'+e(o.label)+'</h3><p class="muted">'+e(o.id)+' · '+e(date(o.captured_at))+'</p><div class="confidence"><strong>'+Math.round(o.confidence*100)+'%</strong> AI Confidence</div>'+link('observations/'+o.id,'観測詳細を見る →')+'</article>';}
function map(data){return '<div class="forest-map" aria-label="森林区画の模式図">'+data.areas.map(a=>'<div class="area" style="left:'+a.bounds.x+'%;top:'+a.bounds.y+'%;width:'+a.bounds.width+'%;height:'+a.bounds.height+'%"><span>'+e(a.id)+'<small>'+e(a.name)+'</small></span></div>').join('')+latestPerSite(data.observations).map(o=>'<a class="marker '+e(o.status.toLowerCase())+'" style="left:'+o.position.x+'%;top:'+o.position.y+'%" href="#observations/'+e(o.id)+'" aria-label="'+e(o.id+' '+o.label)+'">'+(o.status==='NORMAL'?'●':'!')+'</a>').join('')+data.drones.map(d=>'<a class="marker drone" style="left:'+d.position.x+'%;top:'+d.position.y+'%" href="#drone" aria-label="'+e(d.id)+'">✦</a>').join('')+'<span class="north">↑ N</span><span class="map-caption">模式図 · 座標はデモ用</span></div><p class="legend">● 正常　<span>! 要確認 / 異常</span>　✦ 機体　· 地点を選択して詳細へ</p>';}

const statusName=value=>({NORMAL:'正常',REVIEW:'要確認',ANOMALY:'異常'}[value]||value);
const unit=(value,suffix)=>value==null?'未記録':value+' '+suffix;
function captureMetadata(o){return dl([['Observation',o.id],['観測地点',o.site_id||'未記録'],['Area',o.area_id],['Drone ID',o.drone_id],['Mission ID',o.mission_id||'未記録'],['撮影日時',date(o.captured_at)],['緯度 / 経度',o.position.lat+' / '+o.position.lng],['飛行高度',unit(o.altitude_m,'m')],['撮影角度（真下から）',unit(o.camera_angle_deg,'°')],['機首方位',unit(o.heading_deg,'°')],['AIモデル',o.ai_model||'未記録'],['Confidence',Math.round(o.confidence*100)+'%']]);}
function comparison(data,o){
 const previous=previousObservation(data,o);
 const history=observationHistory(data,o);
 const pane=(item,label)=>'<figure class="comparison-pane"><figcaption>'+label+' · '+e(item.id)+'</figcaption><img src="'+e(item.image_url)+'" alt="'+e(label+'のシミュレーション樹冠画像')+'"><div class="row">'+badge(item.status)+'<strong>'+Math.round(item.confidence*100)+'%</strong></div><p class="muted">'+e(date(item.captured_at))+'<br>高度 '+e(unit(item.altitude_m,'m'))+' / 撮影角度 '+e(unit(item.camera_angle_deg,'°'))+'</p></figure>';
 return '<section class="card comparison"><p class="eyebrow">CONTINUOUS OBSERVATION</p><h2>前回と今回を比較</h2><p class="muted">'+e(o.area_id)+' / '+e(o.site_id||'地点未記録')+' · 同じ地点の撮影履歴</p>'+(previous?'<p class="change-summary">'+e(statusName(previous.status))+' → '+e(statusName(o.status))+'<span>'+ (previous.status!==o.status?'判定の変化あり':'判定は同じ')+'</span></p><div class="comparison-grid">'+pane(previous,'前回観測')+pane(o,'今回観測')+'</div>':'<p>この地点の前回観測はまだありません。</p>'+pane(o,'今回観測'))+'<p class="muted">画像はデモ用です。画素差分の解析は行っていません。</p><h3>観測日時の履歴</h3><ol class="observation-timeline">'+history.map(item=>'<li '+(item.id===o.id?'aria-current="true"':'')+'><a href="#observations/'+e(item.id)+'"><time>'+e(date(item.captured_at))+'</time><span>'+e(item.id)+' · '+e(statusName(item.status))+' · '+Math.round(item.confidence*100)+'%</span></a></li>').join('')+'</ol></section>';
}
function missionDetails(m){
 if(m.source==='API'){
  const position=m.target.lat!=null&&m.target.lon!=null
   ? m.target.lat+' / '+m.target.lon
   : '未指定';
  return dl([
   ['要求元','Go API / PostgreSQL'],
   ['対象クラス',m.target.target_class||'未指定'],
   ['緯度 / 経度',position],
   ['目標高度',m.constraints.max_altitude_m!=null?m.constraints.max_altitude_m+' m':'未指定'],
   ['優先度',m.priority||'未記録'],
   ['理由',m.reason],
   ['作成時刻',date(m.created_at)]
  ]);
 }
 return dl([
  ['要求元',m.source==='AI'?'AI自動要求':'ユーザー'],
  ['区域',m.target.area_id||'未指定'],
  ['調査機',m.drone_id||'未指定'],
  ['対象観測',m.target.observation_id||'区域巡回'],
  ['理由',m.reason],
  ['高度上限',m.constraints.max_altitude_m+' m'],
  ['ジオフェンス',m.constraints.geofence_required?'必須':'任意'],
  ['作成時刻',date(m.created_at)]
 ]);
}

function missionFlow(m,data){
 const original=data.observations.find(o=>o.id===m.target.observation_id);
 const result=data.observations.find(o=>o.id===m.result_observation_id);
 const plan=m.capture_plan;
 return '<section class="mission-flow"><div class="row"><h3>'+(m.source==='AI'?'AIが再観測を要求':'再観測の流れ')+'</h3>'+badge(m.source==='AI'?'AI':'USER')+'</div><ol class="flow-steps"><li><strong>AI判定</strong><span>'+(original?Math.round(original.confidence*100)+'%':'未記録')+'</span></li><li><strong>'+e(m.reason)+'</strong><span>'+e(m.id)+' · '+e(m.status)+'</span></li><li><strong>撮影条件を変更</strong><span>'+(plan?'高度 '+e(plan.from_altitude_m)+'m → '+e(plan.altitude_m)+'m<br>撮影角度 '+e(plan.from_camera_angle_deg)+'° → '+e(plan.camera_angle_deg)+'°<br>機首方位 '+e(plan.from_heading_deg)+'° → '+e(plan.heading_deg)+'°':'デモ開始時に設定')+'</span></li><li><strong>再判定</strong><span>'+(result?e(statusName(result.status))+' · '+Math.round(result.confidence*100)+'%':'結果待ち')+'</span></li></ol><p class="muted">自動要求はデモのルール判定（confidence 70%未満）です。実機への指示や実際の再推論は行いません。</p>'+(m.status==='COMPLETED'&&result?link('observations/'+result.id,'再判定結果を見る →'):['REQUESTED','ACCEPTED','RUNNING'].includes(m.status)?'<button type="button" class="primary" data-advance="'+e(m.id)+'" '+(busy?'disabled':'')+'>'+(m.status==='RUNNING'?'再判定デモを完了する':'再観測デモを開始する')+'</button>':'')+'</section>';
}
function detail(data,o){
 const mission=[...data.missions].reverse().find(m=>m.type==='REOBSERVE'&&m.target.observation_id===o.id);
 const existing=data.missions.find(m=>m.type==='REOBSERVE'&&m.target.observation_id===o.id&&['REQUESTED','ACCEPTED','RUNNING'].includes(m.status));
 return link('observations','← 観測一覧')+'<div class="detail observation-detail"><div>'+comparison(data,o)+(mission?'<article class="card reobserve-card">'+missionFlow(mission,data)+'</article>':'')+'</div><article class="card observation-metadata">'+badge(o.status)+'<h2>'+e(o.label)+'</h2><p>'+e(o.note)+'</p><div class="confidence"><strong>'+Math.round(o.confidence*100)+'%</strong> AI Confidence</div><h3>観測メタデータ</h3>'+captureMetadata(o)+(o.parent_observation_id?link('observations/'+o.parent_observation_id,'再観測前の観測を見る'):'')+'<p class="muted">再観測条件：高度上限20m / ジオフェンス必須</p><button class="primary" data-reobserve="'+e(o.id)+'" '+(busy||existing?'disabled':'')+'>'+(existing?'再観測依頼済み · '+e(existing.id):busy?'作成中…':'手動で再観測を依頼する')+'</button>'+link('missions','Mission一覧を見る')+'</article></div>';
}

function render(){
 const {data,persistent}=store.getSnapshot();
 const [raw,id]=location.hash.slice(1).split('/');const view=views.includes(raw)?raw:'home';
 document.querySelector('nav').innerHTML=views.map(v=>'<a href="#'+v+'" '+(v===view?'aria-current="page"':'')+'><span>'+v.toUpperCase()+'</span>'+labels[v]+'</a>').join('');
 let html='<div class="page-heading"><p class="eyebrow">FOREST / '+view.toUpperCase()+'</p><h1>'+labels[view]+'</h1>'+(view==='home'?'':'<p class="muted">森林の変化を見つけ、次の観測につなげる。</p>')+'</div>';
 if(!persistent) html+='<p class="warning">ブラウザーに保存できないため、再読み込みで操作内容がリセットされます。</p>';
 if(view==='home'){
 html+=weatherPanel()+'<section class="card continuity-summary"><p class="eyebrow">FOREST REMEMBERS</p><h2>観測結果</h2><p>同じ地点の履歴を比較し、自信の低い判定からAIが再観測を要求します。</p>'+link('observations/OBS-0184','A-17の時系列比較・再観測を見る →')+'</section><div class="section-title"><h2>登録した調査機</h2>'+link('drone','機体の詳細を見る')+'</div><div class="grid">'+data.drones.map(d=>'<article class="card drone-summary"><div class="row"><h3>'+e(d.id)+'</h3>'+badge(d.status)+'</div><div class="battery"><span style="width:'+d.battery_pct+'%"></span></div>'+dl([['バッテリー',d.battery_pct+'%'],['GPS',d.gps],['Jetson',d.jetson],['最終受信',date(d.last_seen_at)]])+'</article>').join('')+'</div><section class="card dispatch"><div><p class="eyebrow">FIELD REQUEST</p><h2>調査機を稼働・要請する</h2><p class="muted">機体と調査区域を選び、依頼を作成します。</p></div><form id="dispatch-form"><label for="dispatch-drone">調査機</label><select id="dispatch-drone" name="drone_id">'+data.drones.map(d=>'<option value="'+e(d.id)+'">'+e(d.id)+'</option>').join('')+'</select><label for="dispatch-area">調査区域</label><select id="dispatch-area" name="area_id">'+data.areas.map(a=>'<option value="'+e(a.id)+'" '+(a.id===selectedArea?'selected':'')+'>'+e(a.id+' · '+a.name)+'</option>').join('')+'</select><div class="dispatch-actions"><button type="submit" name="type" value="PATROL" '+(busy?'disabled':'')+'>稼働を要請（巡回）</button><button class="primary" type="submit" name="type" value="INSPECT" '+(busy?'disabled':'')+'>調査を要請</button></div><p class="muted">デモでは依頼を記録します。実機の飛行は開始しません。</p></form>'+link('missions','依頼状況を見る →')+'</section><div class="section-title"><h2>最新の観測</h2>'+link('observations','すべてを見る')+'</div><div class="grid">'+latestPerSite(data.observations).sort((a,b)=>Date.parse(b.captured_at)-Date.parse(a.captured_at)).slice(0,2).map(observationCard).join('')+'</div>';

 }
 if(view==='map') html+=map(data)+'<div class="grid">'+data.areas.map(a=>'<article class="card"><h3>'+e(a.id)+' / '+e(a.name)+'</h3>'+badge(a.health)+'</article>').join('')+'</div>';
 if(view==='observations'){
 const o=data.observations.find(o=>o.id===id);
 if(id && !o) html+='<p>観測が見つかりません。</p>'+link('observations','一覧に戻る');
 else if(o){html+=detail(data,o);}
 else html+='<label class="filter">状態 <select id="filter">'+['ALL','NORMAL','REVIEW','ANOMALY'].map(s=>'<option '+(s===filter?'selected':'')+'>'+s+'</option>').join('')+'</select></label><div class="grid">'+[...data.observations].sort((a,b)=>Date.parse(b.captured_at)-Date.parse(a.captured_at)).filter(o=>filter==='ALL'||o.status===filter).map(observationCard).join('')+'</div>';
 }
 if(view==='missions') html+='<p class="muted">REQUESTEDは依頼の作成状態です。実機は自動で飛行しません。</p><div class="grid">'+[...data.missions].reverse().map(m=>'<article class="card"><div class="row"><h2>'+e(m.id)+'</h2>'+badge(m.status)+'</div><h3>'+e(m.type)+'</h3>'+missionDetails(m)+(m.type==='REOBSERVE'?missionFlow(m,data):'')+(m.target.observation_id?link('observations/'+m.target.observation_id,'対象の観測を見る'):'')+'</article>').join('')+'</div>';
 if(view==='drone') html+='<div class="grid">'+data.drones.map(d=>'<article class="card"><p class="eyebrow">SURVEY VEHICLE</p><h2>'+e(d.id)+'</h2>'+badge(d.status)+'<div class="battery"><span style="width:'+d.battery_pct+'%"></span></div>'+dl([['バッテリー',d.battery_pct+'%'],['GPS',d.gps],['Jetson',d.jetson],['高度',d.altitude_m+' m'],['緯度 / 経度',d.position.lat+' / '+d.position.lng],['最終受信',date(d.last_seen_at)]])+'<p class="muted">サンプルの機体テレメトリーです。</p></article>').join('')+'</div>';
 if(view==='log') html+='<div class="timeline">'+data.logs.map(l=>'<article class="card"><p class="eyebrow">'+e(l.event)+'</p><h3>'+e(l.message)+'</h3><p class="muted">'+e(date(l.time))+' · '+e(l.id)+'</p>'+(l.mission_id?link('missions',l.mission_id+'を確認'):'')+'</article>').join('')+'</div>';
 content.innerHTML=html;
}
content.addEventListener('input',event=>{if(event.target.id==='postal')postal=event.target.value;});
content.addEventListener('submit',async event=>{
 if(event.target.id==='weather-form'){event.preventDefault();updateWeather(new FormData(event.target).get('postal'));return;}
 if(event.target.id!=='dispatch-form')return;event.preventDefault();if(busy)return;
 const form=new FormData(event.target);const type=event.submitter?.value||'INSPECT';const drone=form.get('drone_id');selectedArea=form.get('area_id');busy=true;render();
 try{const result=await store.requestDispatch({type,drone_id:drone,area_id:selectedArea});notify(result.duplicate?'依頼済みです：'+result.mission.id:result.mission.id+' を作成し、LOGに記録しました。');}
 catch(error){notify(error.message);}finally{busy=false;render();document.querySelector('#dispatch-area')?.focus();}
});
content.addEventListener('change',event=>{if(event.target.id==='filter'){filter=event.target.value;render();}});
content.addEventListener('click',async event=>{
 if(event.target.closest('#region-delete')){deleteRegion();return;}
 if(event.target.closest('#weather-refresh')){updateWeather(savedPostal);return;}
 const advance=event.target.closest('[data-advance]');
 if(advance){if(busy)return;busy=true;render();try{const result=await store.advanceReobserve(advance.dataset.advance);notify(result.mission.status==='COMPLETED'?'再判定デモを完了し、新しい観測を履歴に追加しました。':'高度・角度を変えた再観測デモを開始しました。');}catch(error){notify(error.message);}finally{busy=false;render();document.querySelector('[data-advance]')?.focus();}return;}
 const button=event.target.closest('[data-reobserve]');if(!button||busy)return;busy=true;render();try{const result=await store.requestReobserve(button.dataset.reobserve);notify(result.duplicate?'既存の依頼 '+result.mission.id+' を確認してください。':result.mission.id+' を作成し、LOGに記録しました。');}catch(error){notify(error.message);}finally{busy=false;render();document.querySelector('[data-reobserve]')?.focus();}});
window.addEventListener('hashchange',()=>{render();content.focus();window.scrollTo(0,0);});
store.subscribe(render);
try{await store.init();render();if(postal)updateWeather(postal);}catch{content.textContent='読み込みに失敗しました。ページを再読み込みしてください。';}