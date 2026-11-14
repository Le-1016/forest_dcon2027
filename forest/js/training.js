import {trainingRequest, setTrainingToken, hasTrainingToken} from './training-api.js';

const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const names = {normal: '通常', fire: '火災', smoke: '煙'};
const statusNames = {QUEUED:'PCの受付待ち', RUNNING:'学習中', COMPLETED:'学習完了', FAILED:'失敗', CANCELLED:'停止済み'};
const terminal = job => ['COMPLETED','FAILED','CANCELLED'].includes(job.status);
const percent = value => Number.isFinite(value) ? (value*100).toFixed(1)+'%' : '—';
const when = value => value ? new Date(value*1000).toLocaleString('ja-JP') : '—';

function chart(metrics, accuracy = false) {
  if (!metrics.length) return '<p class="muted">最初のエポックが完了するとグラフが表示されます。</p>';
  const keys = accuracy ? ['val_accuracy'] : ['train_loss','val_loss'];
  const max = accuracy ? 1 : Math.max(.001, ...metrics.flatMap(m => keys.map(k => m[k])));
  const points = key => metrics.map((m, i) => `${45+i*520/Math.max(1,metrics.length-1)},${170-m[key]/max*140}`).join(' ');
  return '<svg class="ml-chart" viewBox="0 0 600 210" role="img" aria-label="'+(accuracy?'検証正解率':'学習損失と検証損失')+'の推移"><path d="M45 20V170H570" fill="none" stroke="#65806c"/>'+keys.map((k,i)=>'<polyline fill="none" stroke="'+(i?'#f2c86d':'#9cddad')+'" stroke-width="3" points="'+points(k)+'"/>'+metrics.map((m,j)=>'<circle cx="'+(45+j*520/Math.max(1,metrics.length-1))+'" cy="'+(170-m[k]/max*140)+'" r="3" fill="'+(i?'#f2c86d':'#9cddad')+'"/>').join('')).join('')+'<text x="3" y="30">'+(accuracy?'100%':max.toFixed(2))+'</text><text x="20" y="174">0</text><text x="45" y="198">epoch 1</text><text x="505" y="198">epoch '+metrics.length+'</text></svg><p class="muted">'+(accuracy?'検証正解率（画像全体の分類）':'<span class="ml-green">● 学習損失</span>　<span class="ml-gold">● 検証損失</span>')+'</p>';
}

function detail(job) {
  if (!job) return '<p class="muted">学習を依頼すると、ここに進捗と結果が表示されます。</p>';
  const metrics = job.metrics || [];
  const latest = metrics.at(-1);
  const synthetic = job.kind === 'smoke_test';
  const result = job.result;
  return '<div class="section-title"><div><p class="eyebrow">'+escape(job.id)+'</p><h2>'+escape(statusNames[job.status] || job.status)+'</h2></div>'+(!terminal(job)?'<button type="button" data-ml-cancel="'+escape(job.id)+'" '+(job.cancel_requested?'disabled':'')+'>'+(job.cancel_requested?'停止を要求済み':'学習を停止')+'</button>':'')+'</div>'+
    (synthetic?'<p class="warning">合成画像による接続テストです。この正解率は火災・煙の識別性能ではありません。</p>':'<p class="muted">火災・煙・通常の画像分類です。火や煙の位置検出、現場での警報、機体の制御は行いません。</p>')+
    '<p>'+escape(job.worker_id)+' · '+escape(job.dataset_id)+' · '+when(job.created_at)+'</p><progress value="'+metrics.length+'" max="'+job.epochs+'" aria-label="学習の進捗"></progress><p>'+metrics.length+' / '+job.epochs+' エポック · 学習率 '+escape(job.learning_rate)+'</p>'+
    '<div class="ml-metrics"><div><span>学習損失</span><strong>'+ (latest?latest.train_loss.toFixed(4):'—')+'</strong></div><div><span>検証損失</span><strong>'+(latest?latest.val_loss.toFixed(4):'—')+'</strong></div><div><span>検証正解率</span><strong>'+percent(latest?.val_accuracy)+'</strong></div></div>'+
    '<div class="ml-charts"><section><h3>損失の推移</h3>'+chart(metrics)+'</section><section><h3>検証正解率</h3>'+chart(metrics,true)+'</section></div>'+
    (job.error?'<p class="warning">'+escape(job.error)+'</p>':'')+
    (result?'<section><h3>分類結果の内訳</h3><p class="muted">行：正解ラベル / 列：AIの予測。対角線以外は取り違えです。</p><div class="ml-table-wrap"><table class="ml-matrix"><thead><tr><th scope="col">正解 ＼ 予測</th>'+result.classes.map(c=>'<th scope="col">'+escape(names[c] || c)+'</th>').join('')+'</tr></thead><tbody>'+result.confusion_matrix.map((row,i)=>'<tr><th scope="row">'+escape(names[result.classes[i]])+'</th>'+row.map((n,j)=>'<td '+(i===j?'class="ml-diagonal"':'')+'>'+escape(n)+'</td>').join('')+'</tr>').join('')+'</tbody></table></div></section>':'')+
    '<section><h3>学習ログ</h3><pre class="ml-log">'+escape((job.logs || []).join('\n'))+'</pre></section>'+
    (job.status === 'COMPLETED'?'<section><h3>保存されたモデルと結果</h3><p class="muted">モデルは自動配備しません。現場データでの検証後に使用してください。</p>'+Object.entries(job.artifacts).map(([name, artifact])=>'<div class="ml-artifact"><button type="button" data-ml-download="'+escape(job.id)+'/'+escape(name)+'">'+escape(name)+' を保存</button><span>'+Math.round(artifact.bytes/1024)+' KB</span><code>SHA-256 '+escape(artifact.sha256)+'</code></div>').join('')+'</section>':'');
}

export function mountTraining(root) {
  let alive = true, timer, selected = '', data = null, busy = false, draft = null, generation = 0;
  const controller = new AbortController();
  root.innerHTML = '<section class="card ml-intro"><p class="eyebrow">FIRE / SMOKE / NORMAL</p><h2>火災・煙を学習する</h2><p>PCで学習し、FORESTで進捗と結果を確認します。</p><p class="muted">VPS：依頼・結果保存 → GPU搭載PC：学習 → VPS：モデル返却</p><form id="ml-login"><label for="ml-token">学習サービスの認証キー</label><div class="ml-input-row"><input type="password" id="ml-token" autocomplete="off" placeholder="管理者が設定した認証キー" '+(hasTrainingToken()?'':'required')+'><button type="submit">接続する</button><button type="button" id="ml-logout">認証を削除</button></div></form><p id="ml-message" role="status" aria-live="polite"></p></section><div id="ml-dashboard" hidden><div class="ml-layout"><section class="card"><h2>学習を依頼</h2><form id="ml-create"><label for="ml-worker">学習するPC</label><select id="ml-worker" name="worker_id" required></select><div id="ml-device" class="muted"></div><label for="ml-kind">学習内容</label><select id="ml-kind" name="kind"><option value="image_classification">火災・煙・通常の画像分類</option><option value="smoke_test">接続テスト（合成画像）</option></select><label for="ml-dataset">データセット</label><select id="ml-dataset" name="dataset_id" required></select><div id="ml-dataset-info"></div><div class="ml-form-grid"><label>エポック数<input name="epochs" type="number" min="1" max="100" value="10" required></label><label>学習率<input name="learning_rate" type="number" min="0.00001" max="0.1" step="any" value="0.001" required></label></div><button type="submit" class="primary" id="ml-submit">学習を依頼する</button><p class="muted">データはPCの承認済みフォルダーから読みます。画像をGitHubへ公開する必要はありません。</p></form></section><section class="card"><h2>学習履歴</h2><div id="ml-jobs"></div><p id="ml-updated" class="muted"></p></section></div><section class="card" id="ml-detail"></section></div>';
  const message = (text, error = false) => { const node = root.querySelector('#ml-message'); node.textContent = text; node.classList.toggle('warning', error); };
  const el = selector => root.querySelector(selector);

  function options() {
    if (!data) return;
    const select = el('#ml-worker');
    const current = select.value;
    const html = data.workers.map(w=>'<option value="'+escape(w.id)+'">'+escape(w.id)+(w.online?' · 接続中':' · オフライン')+'</option>').join('') || '<option value="">PCが未登録です</option>';
    if (select.innerHTML !== html) { select.innerHTML = html; if (data.workers.some(w=>w.id===current)) select.value = current; }
    const worker = data.workers.find(w=>w.id===select.value);
    el('#ml-device').textContent = worker ? worker.device+' · '+(worker.online?'接続中':'切断中') : 'PCでワーカーを起動してください。';
    const datasets = el('#ml-dataset');
    const previous = datasets.value;
    const synthetic = el('#ml-kind').value === 'smoke_test';
    const dsHtml = synthetic?'<option value="synthetic">合成画像（動作確認専用）</option>':worker?.datasets.map(d=>'<option value="'+escape(d.id)+'">'+escape(d.id)+(d.ready?'':' · 準備が必要')+'</option>').join('') || '<option value="">データセットをPCで登録してください</option>';
    if (datasets.innerHTML !== dsHtml) { datasets.innerHTML = dsHtml; if ([...datasets.options].some(o=>o.value===previous)) datasets.value = previous; }
    const ds = worker?.datasets.find(d=>d.id===datasets.value);
    el('#ml-dataset-info').innerHTML = synthetic?'<p class="warning">合成画像の正解率は火災・煙の性能評価に使えません。</p>':ds?'<div class="ml-table-wrap"><table class="ml-matrix"><thead><tr><th>ラベル</th><th>学習用</th><th>検証用</th></tr></thead><tbody>'+['normal','fire','smoke'].map(c=>'<tr><th>'+names[c]+'</th><td>'+escape(ds.counts?.train?.[c] ?? 0)+'</td><td>'+escape(ds.counts?.val?.[c] ?? 0)+'</td></tr>').join('')+'</tbody></table></div>'+(ds.errors || []).map(e=>'<p class="warning">'+escape(e)+'</p>').join(''):'<p class="muted">PC上に train と val の各フォルダーを用意し、それぞれ normal / fire / smoke に画像を配置します。</p>';
    el('#ml-submit').disabled = busy || !worker?.online || (!synthetic && !ds?.ready) || data.jobs.some(j=>j.worker_id===worker?.id && !terminal(j));
  }

  function update() {
    options();
    el('#ml-jobs').innerHTML = data.jobs.length?data.jobs.map(j=>'<button type="button" class="ml-job '+(j.id===selected?'ml-selected':'')+'" data-ml-job="'+escape(j.id)+'"><strong>'+escape(statusNames[j.status])+'</strong><span>'+escape(j.kind==='smoke_test'?'接続テスト':j.dataset_id)+' · '+j.metrics.length+'/'+j.epochs+' epoch</span><small>'+when(j.created_at)+'</small></button>').join(''):'<p class="muted">まだ学習履歴はありません。</p>';
    const focused = document.activeElement;
    const detailFocused = el('#ml-detail').contains(focused);
    const action = focused?.getAttribute('data-ml-cancel') ? '[data-ml-cancel]' : null;
    el('#ml-detail').innerHTML = detail(data.jobs.find(j=>j.id===selected));
    if (detailFocused && action) el('#ml-detail').querySelector(action)?.focus({preventScroll:true});
    el('#ml-updated').textContent = '最終更新 '+new Date().toLocaleTimeString('ja-JP')+' · 3秒ごとに更新';
  }

  async function refresh() {
    clearTimeout(timer);
    const version = generation;
    try {
      const next = await trainingRequest('/state', undefined, {signal:controller.signal});
      if (!alive || version !== generation) return;
      data = next; if (!data.jobs.some(j=>j.id===selected)) selected = data.jobs[0]?.id || '';
      el('#ml-dashboard').hidden = false;
      message('学習サービスに接続中。画像と数値は実際の学習結果です。'); update();
    } catch (error) {
      if (!alive || version !== generation) return;
      message(error.name === 'AbortError'?'通信が中断されました。':error.message,true);
      if (data) el('#ml-updated').textContent = '接続が切れています。表示は最後に取得した値です。';
      if (error.status === 401) { el('#ml-dashboard').hidden = true; return; }
    }
    if (alive) timer = setTimeout(refresh,3000);
  }

  root.addEventListener('change', event => { if (['ml-worker','ml-kind','ml-dataset'].includes(event.target.id)) { draft = null; options(); } }, {signal:controller.signal});
  root.addEventListener('submit', async event => {
    event.preventDefault();
    if (event.target.id === 'ml-login') {
      generation += 1;
      if (el('#ml-token').value.trim()) setTrainingToken(el('#ml-token').value);
      el('#ml-token').value = ''; await refresh(); return;
    }
    if (event.target.id !== 'ml-create' || busy) return;
    busy = true; options();
    const fields = Object.fromEntries(new FormData(event.target));
    const settings = {...fields, epochs:Number(fields.epochs), learning_rate:Number(fields.learning_rate)};
    // Keep the id for a network retry with the same settings.
    const signature = JSON.stringify(settings);
    if (!draft || draft.signature !== signature) draft = {signature, id:crypto.randomUUID()};
    try {
      const job = await trainingRequest('/jobs',{...settings, request_id:draft.id});
      if (!alive) return;
      selected = job.id; draft = null; await refresh();
    } catch(error) { if(alive) message(error.message,true); }
    finally {busy = false; if(alive) options();}
  }, {signal:controller.signal});
  root.addEventListener('click', async event => {
    const button = event.target.closest('button'); if (!button) return;
    if (button.id === 'ml-logout') {generation+=1; setTrainingToken(''); clearTimeout(timer); data=null; el('#ml-dashboard').hidden=true; message('認証キーを削除しました。'); return;}
    if (button.dataset.mlJob) {selected=button.dataset.mlJob; update(); return;}
    try {
      if (button.dataset.mlCancel) {button.disabled=true; await trainingRequest('/jobs/'+button.dataset.mlCancel+'/cancel',{}); if(alive) await refresh();}
      if (button.dataset.mlDownload) {
        button.disabled=true;
        const [id,name] = button.dataset.mlDownload.split('/');
        const blob = await trainingRequest('/jobs/'+id+'/artifacts/'+name,undefined,{download:true});
        if (!alive) return;
        const a=document.createElement('a'),url=URL.createObjectURL(blob); a.href=url; a.download=id+'-'+name; a.click(); setTimeout(()=>URL.revokeObjectURL(url),1000);
      }
    } catch(error) {if(alive) message(error.message,true);}
    finally {if(button.isConnected) button.disabled=false;}
  }, {signal:controller.signal});
  if(hasTrainingToken()) refresh();
  return () => {alive=false;clearTimeout(timer);controller.abort();};
}
