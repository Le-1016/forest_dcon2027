# FOREST App v0.1

静的な森林観測SPA。外部サービス・ビルド・地図APIは不要です。
GitHub Pagesがリポジトリルートを配信していれば /forest/ で動作します。
相対パスとハッシュルーティングを使用するため、詳細画面も再読み込みできます。

## ローカル起動

リポジトリルートで python3 -m http.server 8000 を実行し、http://localhost:8000/forest/ を開いてください。
ES Modulesを使用するため、file:// での直接起動は対象外です。

## 操作

HOME → 要確認の観測 → OBS-0184（Confidence 54%）→ 再観測を依頼する
→ MISSIONSのREOBSERVE / REQUESTED → LOGの生成記録を確認。
同じ観測の進行中依頼は重複生成しません。ブラウザーの戻る・進むにも対応します。
デモ状態はlocalStorageの forest.mock.v1 に保存します。保存不可の場合はメモリーで動作します。
サンプル画像・位置・テレメトリーは架空で、実機への送信はありません。

## 境界と将来の接続

- mock-data.js: Area / Drone / Observation / Mission とログの初期DTO。
- store.js: async repository (load / requestReobserve)、状態通知、永続化、重複防止。
- app.js: 6画面、ハッシュナビゲーション、ユーザー操作。保存処理を持ちません。
- assets/canopy.svg: 外部通信を必要としないシミュレーション観測画像。

createStoreにGo API repositoryを渡すことでUIを維持して置換できます。
loadは {data, persistent}、requestReobserveは {mission, duplicate} を返します。
Go側でPostgreSQLへのMission作成と監査ログを同一トランザクションにし、
同一観測の進行中Missionを一意制約・冪等性キーで保護してください。
Mission DTOは target.area_id / observation_id、reason、constraints.max_altitude_m /
geofence_required を持ちます。Jetson / ROS 2 / PX4への配送・受理・実行状態は
バックエンドが担い、REQUESTEDだけで飛行開始とみなしません。
実機接続では認証・承認・ジオフェンス検証・通信断処理が別途必要です。
