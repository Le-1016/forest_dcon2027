import { mockData, shortObservationLabel } from './mock-data.js';
import { latestPerSite } from './observation-history.js';

// Repository methods are async so a Go API can replace this local demo adapter.
// Production: generate missions/audit records atomically on the backend,
// enforce idempotency per observation, and validate flight constraints there.
const copy = value => JSON.parse(JSON.stringify(value));
const key = 'forest.mock.v1';
const active = mission => ['REQUESTED', 'ACCEPTED', 'RUNNING'].includes(mission.status);
const apiMission = row => ({
  id: row.mission_id,
  type: row.mission_type,
  status: row.status,
  source: 'API',
  drone_id: null,
  target: {
    area_id: null,
    observation_id: null,
    target_class: row.target_class,
    lat: row.target_lat,
    lon: row.target_lon
  },
  reason: row.reason || '未記録',
  priority: row.priority || '未記録',
  constraints: {
    max_altitude_m: row.target_alt,
    geofence_required: false
  },
  created_at: row.created_at
});

async function fetchApiMissions() {
  const response = await fetch('/api/missions');
  if (!response.ok) throw new Error('Mission APIの取得に失敗しました。');
  const rows = await response.json();
  return rows.map(apiMission);
}
export const LOW_CONFIDENCE_THRESHOLD = 0.7;
function valid(state) {
  return state && ['areas','drones','observations','missions','logs'].every(k => Array.isArray(state[k])) &&
    state.areas.every(a => a.id && a.bounds) && state.drones.every(d => d.id && d.position) &&
    state.observations.every(o => o.id && o.position && typeof o.confidence === 'number') &&
    state.missions.every(m => m.id && m.target && m.constraints) && state.logs.every(l => l.id && l.time);
}
function migrate(saved) {
  const state = copy(saved);
  const defaults = new Map(mockData.observations.map(o => [o.id, o]));
  state.observations = state.observations.map(o => ({...defaults.get(o.id), ...o, label:shortObservationLabel(o.label)}));
  for (const fixture of mockData.observations) {
    if (!state.observations.some(o => o.id === fixture.id)) state.observations.push(copy(fixture));
  }
  state.missions = state.missions.map(m => ({source:'USER', ...m}));
  state.schema_version = 2;
  return state;
}
export function createMockRepository(storage) {
  let state = migrate(mockData), persistent = Boolean(storage);
  try {
    const saved = storage?.getItem(key);
    if (saved) { const parsed = JSON.parse(saved); if(valid(parsed)) state = migrate(parsed); }
  } catch { persistent = false; }
  const nextId = (prefix, rows) => prefix + String(Math.max(0,...rows.map(r=>Number(r.id.split('-')[1])||0))+1).padStart(4,'0');
  function persist() {
    try { if (!storage) persistent = false; else storage.setItem(key, JSON.stringify(state)); }
    catch { persistent = false; }
  }
  function log(event, message, fields={}) {
    state.logs.unshift({id:nextId('LOG-',state.logs),time:new Date().toISOString(),event,message,...fields});
  }
  function makeReobserve(observation, source) {
    const prior = state.missions.find(m => m.type === 'REOBSERVE' && m.target.observation_id === observation.id && (source === 'AI' || active(m)));
    if (prior) return {mission:copy(prior),duplicate:true};
    const mission = {
      id:nextId('MIS-',state.missions),type:'REOBSERVE',status:'REQUESTED',source,
      drone_id:observation.drone_id,
      target:{area_id:observation.area_id,site_id:observation.site_id,observation_id:observation.id},
      reason:observation.confidence<LOW_CONFIDENCE_THRESHOLD?'LOW_CONFIDENCE':'MANUAL_REVIEW',
      constraints:{max_altitude_m:20,geofence_required:true},
      capture_plan:{from_altitude_m:observation.altitude_m??15,altitude_m:8,from_camera_angle_deg:observation.camera_angle_deg??45,camera_angle_deg:25,from_heading_deg:observation.heading_deg??90,heading_deg:135},
      created_at:new Date().toISOString()
    };
    state.missions.push(mission);
    log(source==='AI'?'AI_REOBSERVE_REQUESTED':'MISSION_REQUESTED',
      (source==='AI'?'AIが確信度'+Math.round(observation.confidence*100)+'%を検出し、':'')+observation.id+'の再観測Mission '+mission.id+'を生成しました。',
      {source,mission_id:mission.id,observation_id:observation.id,reason:mission.reason});
    return {mission:copy(mission),duplicate:false};
  }
  function evaluateLatest() {
    for (const observation of latestPerSite(state.observations)) {
      if (observation.confidence < LOW_CONFIDENCE_THRESHOLD) makeReobserve(observation,'AI');
    }
  }
  evaluateLatest();
  persist();
  return {
    async load() {
      const data = copy(state);
      const apiMissions = await fetchApiMissions();
      const apiIds = new Set(apiMissions.map(m => m.id));
      data.missions = [
        ...data.missions.filter(m => !apiIds.has(m.id)),
        ...apiMissions
      ];
      return {data,persistent};
    },
    async requestDispatch({type,drone_id,area_id}) {
      if (!['PATROL','INSPECT'].includes(type)) throw new Error('依頼の種類が不正です。');
      const drone = state.drones.find(d=>d.id===drone_id);
      if (!drone || !state.areas.some(a=>a.id===area_id)) throw new Error('機体または区域が見つかりません。');
      if (drone.status!=='STANDBY') throw new Error('待機中の機体を選んでください。');
      const existing = state.missions.find(m=>m.drone_id===drone_id && active(m));
      if (existing) return {mission:copy(existing),duplicate:true};
      const mission={id:nextId('MIS-',state.missions),drone_id,type,status:'REQUESTED',source:'USER',target:{area_id,observation_id:null},reason:'MANUAL_REQUEST',constraints:{max_altitude_m:20,geofence_required:true},created_at:new Date().toISOString()};
      state.missions.push(mission);
      log('MISSION_REQUESTED',drone_id+'の'+(type==='PATROL'?'巡回':'調査')+'Mission '+mission.id+'を要請しました。',{source:'USER',mission_id:mission.id,drone_id});
      persist(); return {mission:copy(mission),duplicate:false};
    },
    async requestReobserve(id) {
      const observation=state.observations.find(o=>o.id===id);
      if (!observation) throw new Error('観測が見つかりません。');
      const result=makeReobserve(observation,'USER');persist();return result;
    },
    async advanceReobserve(id) {
      const mission=state.missions.find(m=>m.id===id && m.type==='REOBSERVE');
      if (!mission) throw new Error('再観測Missionが見つかりません。');
      if (mission.status==='COMPLETED') return {mission:copy(mission),duplicate:true};
      const observation=state.observations.find(o=>o.id===mission.target.observation_id);
      if (!observation) throw new Error('元の観測が見つかりません。');
      if (['REQUESTED','ACCEPTED'].includes(mission.status)) {
        const existing=state.missions.find(m=>m.id!==id && m.drone_id===mission.drone_id && m.status==='RUNNING');
        if (existing) throw new Error('この機体では別のMissionが実行中です。');
        mission.capture_plan ??= {from_altitude_m:observation.altitude_m??15,altitude_m:8,from_camera_angle_deg:observation.camera_angle_deg??45,camera_angle_deg:25,from_heading_deg:observation.heading_deg??90,heading_deg:135};
        mission.drone_id ??= observation.drone_id;
        mission.status='RUNNING';mission.started_at=new Date().toISOString();
        log('DEMO_REOBSERVE_STARTED',mission.id+'：高度'+mission.capture_plan.from_altitude_m+'m → '+mission.capture_plan.altitude_m+'m、別角度からの再観測デモを開始。',{mission_id:id,source:'DEMO'});
      } else if (mission.status==='RUNNING') {
        const captured_at=new Date(Math.max(Date.now(),Date.parse(observation.captured_at)+1000)).toISOString();
        const result={...copy(observation),id:nextId('OBS-',state.observations),mission_id:id,parent_observation_id:observation.id,captured_at,altitude_m:mission.capture_plan.altitude_m,camera_angle_deg:mission.capture_plan.camera_angle_deg,heading_deg:mission.capture_plan.heading_deg,status:'ANOMALY',label:'変色',confidence:0.92,image_url:'./assets/canopy-reobserve.svg',note:'デモ再判定：近距離・別角度で変色候補を再確認しました。実際の推論結果ではありません。'};
        state.observations.push(result);mission.result_observation_id=result.id;mission.status='COMPLETED';mission.completed_at=captured_at;
        log('DEMO_REASSESSMENT_COMPLETED',mission.id+'：再判定92%、要確認 → 異常。'+result.id+'を記録しました。',{mission_id:id,observation_id:result.id,source:'DEMO'});
        evaluateLatest();
      } else throw new Error('このMissionはデモを進められない状態です。');
      persist();return {mission:copy(mission),duplicate:false};
    }
  };
}
export function createStore(repository) {
  let snapshot,pending=false;const listeners=new Set();
  async function refresh(){snapshot=await repository.load();listeners.forEach(fn=>fn());}
  async function mutate(method,value){if(pending)throw new Error('処理中です。');pending=true;try{const result=await repository[method](value);await refresh();return result;}finally{pending=false;}}
  return {init:refresh,getSnapshot:()=>copy(snapshot),subscribe(fn){listeners.add(fn);return()=>listeners.delete(fn);},requestDispatch:request=>mutate('requestDispatch',request),requestReobserve:id=>mutate('requestReobserve',id),advanceReobserve:id=>mutate('advanceReobserve',id)};
}
let storage;try{storage=globalThis.localStorage;}catch{}
export const store=createStore(createMockRepository(storage));
