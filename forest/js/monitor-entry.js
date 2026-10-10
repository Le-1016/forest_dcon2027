const main = document.querySelector('main');
const disconnected = message => {
  main.replaceChildren();
  const title = document.createElement('h1'); title.textContent = 'VPS専用の管理画面';
  const text = document.createElement('p'); text.textContent = message;
  const link = document.createElement('a'); link.href = './'; link.className = 'button'; link.textContent = '作品紹介へ戻る';
  main.append(title, text, link);
};
if (location.hostname.endsWith('.github.io')) {
  disconnected('GitHub Pagesでは運用APIに接続しません。管理画面はVPS側で開いてください。');
} else {
  try {
    const response = await fetch('/api/health', {signal: AbortSignal.timeout(5000), cache: 'no-store'});
    if (!response.ok || (await response.text()).trim() !== 'ok') throw new Error('Unavailable');
    await import('./app.js');
  } catch {
    disconnected('運用APIに接続できません。VPSのWebサービスとAPIの稼働状況を確認してください。');
  }
}
