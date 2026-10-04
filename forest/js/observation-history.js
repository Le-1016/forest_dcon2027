/** Compare only the same survey point, never arbitrary observations in one area. */
export function observationHistory(data, observation) {
  if (!observation.site_id) return [observation];
  return data.observations
    .filter(item => item.area_id === observation.area_id && item.site_id === observation.site_id)
    .sort((a, b) => Date.parse(a.captured_at) - Date.parse(b.captured_at) || a.id.localeCompare(b.id));
}
export function previousObservation(data, observation) {
  return observationHistory(data, observation)
    .filter(item => Date.parse(item.captured_at) < Date.parse(observation.captured_at))
    .at(-1) || null;
}
export function latestPerSite(observations) {
  const latest = new Map();
  for (const observation of observations) {
    const key = observation.site_id ? observation.area_id + '/' + observation.site_id : observation.id;
    const existing = latest.get(key);
    if (!existing || Date.parse(observation.captured_at) > Date.parse(existing.captured_at)) latest.set(key, observation);
  }
  return [...latest.values()];
}
