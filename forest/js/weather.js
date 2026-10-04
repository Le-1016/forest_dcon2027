// Postal lookup, approximate regional coordinates and weather are isolated from UI.
async function json(url, fetcher) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 12000);
  try {
    const response = await fetcher(url, { signal: controller.signal });
    if (!response.ok) throw new Error('気象サービスに接続できません。時間をおいて再度お試しください。');
    return await response.json();
  } finally { clearTimeout(timer); }
}
export function weatherAppearance(code, day = 1) {
  if (code === 0) return { label: '晴れ', theme: day ? 'clear' : 'night', icon: day ? '☀' : '☾' };
  if ([1, 2].includes(code)) return { label: '晴れ時々曇り', theme: day ? 'clear' : 'night', icon: '⛅' };
  if (code === 3) return { label: '曇り', theme: 'cloudy', icon: '☁' };
  if ([45, 48].includes(code)) return { label: '霧', theme: 'cloudy', icon: '≋' };
  if ([71,73,75,77,85,86].includes(code)) return { label: '雪', theme: 'snow', icon: '❄' };
  if ([95,96,99].includes(code)) return { label: '雷雨', theme: 'rain', icon: 'ϟ' };
  if ([51,53,55,56,57,61,63,65,66,67,80,81,82].includes(code)) return { label: '雨', theme: 'rain', icon: '☂' };
  return { label: '天候不明', theme: 'cloudy', icon: '—' };
}
export async function lookupWeather(input, fetcher = fetch) {
  const postal = input.normalize('NFKC').replace(/[-\s]/g, '');
  if (!/^\d{7}$/.test(postal)) throw new Error('郵便番号を7桁で入力してください。');
  const address = await json('https://zipcloud.ibsnet.co.jp/api/search?zipcode=' + postal, fetcher);
  if (address.status !== 200 || !address.results?.length) throw new Error('郵便番号に対応する地域が見つかりません。');
  const regions = [...new Set(address.results.map(a => a.address1 + a.address2))];
  if (regions.length !== 1) throw new Error('複数の市区町村に該当するため、この郵便番号では地域を特定できません。');
  const region = regions[0];
  const points = await json('https://msearch.gsi.go.jp/address-search/AddressSearch?q=' + encodeURIComponent(region), fetcher);
  const point = points.find(p => p.properties?.title === region) || points.find(p => p.properties?.title?.startsWith(region));
  const [longitude, latitude] = point?.geometry?.coordinates || [];
  if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) throw new Error('地域の位置情報を取得できません。');
  const query = new URLSearchParams({latitude, longitude, current:'temperature_2m,relative_humidity_2m,precipitation,weather_code,wind_speed_10m,wind_gusts_10m,is_day',wind_speed_unit:'ms',timezone:'Asia/Tokyo',forecast_days:'1'});
  const forecast = await json('https://api.open-meteo.com/v1/forecast?' + query, fetcher);
  const current = forecast.current;
  if (!current || !['temperature_2m','wind_speed_10m','weather_code','precipitation','relative_humidity_2m','wind_gusts_10m'].every(k => Number.isFinite(current[k])) || !current.time) throw new Error('気象データを取得できません。');
  return {postal, region, latitude, longitude, current, appearance:weatherAppearance(current.weather_code,current.is_day)};
}
