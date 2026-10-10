(() => {
  const action = document.querySelector('#demo-action');
  const status = document.querySelector('#demo-status');
  let stage = 0;
  const update = () => {
    document.querySelector('#step-two').classList.toggle('active', stage >= 1);
    document.querySelector('#step-three').classList.toggle('active', stage >= 2);
    document.querySelector('#confidence').innerHTML = stage === 2 ? '92<span>%</span>' : '54<span>%</span>';
    const image = document.querySelector('#current-image');
    image.src = stage === 2 ? './assets/canopy-reobserve.svg' : './assets/canopy.svg';
    image.alt = stage === 2 ? '再観測の模式画像：異なる角度で確認した樹冠' : '今回観測の模式画像：一部が変色した樹冠';
    document.querySelector('#demo-description').textContent = ['信頼度が低いため、別の高度・角度から再観測を要求します。','REOBSERVE依頼を生成しました。高度を15mから8mへ変更し、別角度から確認する計画です。','再観測のデモ結果を履歴へ追加しました。信頼度の変化を確認できます。'][stage];
    action.textContent = ['AIの再観測依頼を生成 →','再観測のデモ結果を見る →','デモ完了'][stage];
    action.disabled = stage === 2;
    status.textContent = ['操作待ち · ブラウザー内のデモ','REQUESTED · LOW_CONFIDENCE · デモログへ記録','COMPLETED · 信頼度 54% → 92% · デモログへ記録'][stage];
  };
  action.addEventListener('click', () => { if (stage < 2) { stage += 1; update(); } });
  document.querySelector('#demo-reset').addEventListener('click', () => {stage = 0; update(); action.focus();});
})();
