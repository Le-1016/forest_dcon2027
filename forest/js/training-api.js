const base = '/api/ml';
let token = '';
try { token = sessionStorage.getItem('forest.ml.token') || ''; } catch {}
export function setTrainingToken(value) {
  token = value.trim();
  try { if (token) sessionStorage.setItem('forest.ml.token', token); else sessionStorage.removeItem('forest.ml.token'); } catch {}
}
export const hasTrainingToken = () => Boolean(token);
export async function trainingRequest(path, body, {download = false, signal} = {}) {
  const response = await fetch(base + path, {
    method: body === undefined ? 'GET' : 'POST',
    headers: {'Authorization': 'Bearer ' + token, ...(body === undefined ? {} : {'Content-Type': 'application/json'})},
    body: body === undefined ? undefined : JSON.stringify(body),
    cache: 'no-store', redirect: 'error', signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(10000)]) : AbortSignal.timeout(10000),
  });
  if (!response.ok) {
    let message = response.status === 401 ? '認証キーを確認してください。' : response.status === 502 || response.status === 503 ? '学習サービスに接続できません。サーバーの起動を確認してください。' : '学習サービスとの通信に失敗しました。';
    try { const data = await response.json(); if (typeof data.error === 'string') message = data.error; } catch {}
    const error = new Error(message); error.status = response.status; throw error;
  }
  if (download) return response.blob();
  const data = await response.json();
  return data;
}
