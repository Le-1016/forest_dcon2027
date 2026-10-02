import { mockData } from './mock-data.js';
/** Area, Drone, Observation and Mission DTOs use API-friendly snake_case fields.
 * Replace the repository below with a Go API client. Keep DTOs and async contract.
 * Mission creation and its audit log must become one server-side transaction.
 */
const copy = value => JSON.parse(JSON.stringify(value));
const key = 'forest.mock.v1';
function valid(s) {
 return s && ['areas','drones','observations','missions','logs'].every(k => Array.isArray(s[k])) &&
 s.areas.every(a=>a.id && a.bounds) && s.drones.every(d=>d.id && d.position) &&
 s.observations.every(o=>o.id && o.position && typeof o.confidence==='number') &&
 s.missions.every(m=>m.id && m.target && m.constraints) && s.logs.every(l=>l.id && l.time);
}
export function createMockRepository(storage) {
 let state = copy(mockData), persistence = true;
 try { const saved = storage?.getItem(key); if (saved) { const parsed=JSON.parse(saved); if(valid(parsed)) state=parsed; } } catch { persistence=false; }
 const nextId = (prefix, rows) => prefix + String(Math.max(0,...rows.map(r=>Number(r.id.split('-')[1])||0))+1).padStart(4,'0');
 return {
 async load() { return {data:copy(state),persistent:persistence}; },
 async requestReobserve(observationId) {
 const observation=state.observations.find(o=>o.id===observationId);
 if(!observation) throw new Error('観測が見つかりません。');
 const existing=state.missions.find(m=>m.type==='REOBSERVE' && m.target.observation_id===observationId && ['REQUESTED','ACCEPTED','RUNNING'].includes(m.status));
 if(existing) return {mission:copy(existing),duplicate:true};
 const created_at=new Date().toISOString();
 const mission={id:nextId('MIS-',state.missions),type:'REOBSERVE',status:'REQUESTED',target:{area_id:observation.area_id,observation_id:observation.id},reason:observation.confidence<0.7?'LOW_CONFIDENCE':'MANUAL_REVIEW',constraints:{max_altitude_m:20,geofence_required:true},created_at};
 const log={id:nextId('LOG-',state.logs),time:created_at,event:'MISSION_REQUESTED',mission_id:mission.id,observation_id:observation.id,message:observation.id+'の再観測Mission '+mission.id+'を生成しました。'};
 state={...state,missions:[...state.missions,mission],logs:[log,...state.logs]};
 try { if(!storage) persistence=false; else storage.setItem(key,JSON.stringify(state)); } catch { persistence=false; }
 return {mission:copy(mission),duplicate:false};
 }
 };
}
export function createStore(repository) {
 let snapshot, pending=false;
 const listeners=new Set();
 async function refresh() { snapshot=await repository.load(); listeners.forEach(fn=>fn()); }
 return {init:refresh,getSnapshot:()=>copy(snapshot),subscribe(fn){listeners.add(fn);return()=>listeners.delete(fn);},
 async requestReobserve(id) { if(pending) throw new Error('処理中です。'); pending=true; try { const result=await repository.requestReobserve(id); await refresh(); return result; } finally {pending=false;} }
 };
}
let storage; try {storage=globalThis.localStorage;} catch {}
export const store=createStore(createMockRepository(storage));