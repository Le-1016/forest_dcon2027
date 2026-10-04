/** Mock fixtures. Coordinates are illustrative, not real survey locations. */
export const mockData = {
 areas: [
 {id:'A-17',name:'北側・針葉樹区画',health:'REVIEW',bounds:{x:12,y:12,width:34,height:34}},
 {id:'A-18',name:'中央・混交林区画',health:'NORMAL',bounds:{x:50,y:12,width:36,height:34}},
 {id:'A-19',name:'南側・渓流区画',health:'ANOMALY',bounds:{x:12,y:51,width:74,height:34}}],
 drones:[{id:'FOREST-01',status:'STANDBY',battery_pct:82,gps:'FIX',jetson:'READY',position:{x:68,y:30,lat:35.0012,lng:139.0018},altitude_m:0,last_seen_at:'2026-10-02T06:30:00Z'}],
 observations:[
 {id:'OBS-0174',site_id:'S-17-01',area_id:'A-17',drone_id:'FOREST-01',mission_id:null,status:'NORMAL',label:'正常',confidence:0.96,captured_at:'2026-09-25T06:28:00Z',position:{x:30,y:28,lat:35.0017,lng:139.0008},altitude_m:15,camera_angle_deg:45,heading_deg:90,ai_model:'forest-canopy-demo-v0.1',image_url:'./assets/canopy-before.svg',note:'前回の同一地点の観測。樹冠に顕著な変色は見られません。'},
 {id:'OBS-0184',site_id:'S-17-01',mission_id:'MIS-0001',altitude_m:15,camera_angle_deg:45,heading_deg:90,ai_model:'forest-canopy-demo-v0.1',area_id:'A-17',drone_id:'FOREST-01',status:'REVIEW',label:'変色',confidence:0.54,captured_at:'2026-10-02T06:28:00Z',position:{x:30,y:28,lat:35.0017,lng:139.0008},image_url:'./assets/canopy.svg',note:'光の反射と葉の変色を区別できません。別の角度から再観測が必要です。'},
 {id:'OBS-0183',site_id:'S-19-01',mission_id:'MIS-0001',altitude_m:15,camera_angle_deg:45,heading_deg:90,ai_model:'forest-canopy-demo-v0.1',area_id:'A-19',drone_id:'FOREST-01',status:'ANOMALY',label:'倒木',confidence:0.93,captured_at:'2026-10-02T06:24:00Z',position:{x:39,y:66,lat:35.0005,lng:139.0011},image_url:'./assets/canopy.svg',note:'林床に線状の異常を検出。現地確認候補です。'},
 {id:'OBS-0182',site_id:'S-18-01',mission_id:'MIS-0001',altitude_m:15,camera_angle_deg:45,heading_deg:90,ai_model:'forest-canopy-demo-v0.1',area_id:'A-18',drone_id:'FOREST-01',status:'NORMAL',label:'正常',confidence:0.97,captured_at:'2026-10-02T06:18:00Z',position:{x:62,y:39,lat:35.0012,lng:139.0017},image_url:'./assets/canopy.svg',note:'今回の観測では顕著な異常は検出されませんでした。'}],
 missions:[{id:'MIS-0001',type:'PATROL',status:'COMPLETED',target:{area_id:'A-17',observation_id:null},reason:'SCHEDULED',constraints:{max_altitude_m:20,geofence_required:true},created_at:'2026-10-02T06:00:00Z'}],
 logs:[{id:'LOG-0001',time:'2026-10-02T06:30:00Z',event:'PATROL_COMPLETED',mission_id:'MIS-0001',message:'巡回Mission MIS-0001が完了しました。'}]
};
// Normalize previously saved demo labels without changing their confidence/status.
export function shortObservationLabel(label) {
 const labels={'樹冠の変色の可能性':'変色','樹冠の変色を再確認':'変色','倒木の可能性':'倒木','樹冠の状態は正常':'正常'};
 return labels[label] || label;
}
