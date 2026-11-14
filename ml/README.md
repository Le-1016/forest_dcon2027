# FOREST 火災と煙の機械学習モニター

FOREST Appの「機械学習」から学習を依頼し、GPU搭載PCでPyTorchを実行します。学習損失・検証損失・検証正解率・分類の内訳・ログを表示し、モデルとJSON結果を保存できます。公開の作品紹介ページからは読み込まれません。

初期版は画像全体を `normal`（通常）・`fire`（火災）・`smoke`（煙）の3クラスに分類する小さなCNNです。物体の位置検出、動画追跡、現場での警報、Jetsonへの自動配備、ドローン制御は含みません。現場での識別性能は実画像で別途検証が必要です。

## まずWindows PCだけで使う

既存の `forest_gpu` 環境（CUDA対応PyTorch、NumPy、Pillow）を使えます。リポジトリのルートで次を実行します。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\ml\start-local.ps1
```

ブラウザーが開き、認証キーがクリップボードに入ります。「学習サービスの認証キー」へ貼り付けて接続してください。PCの接続表示が出たら「接続テスト（合成画像）」を選んで学習を依頼できます。合成画像の正解率は火災・煙の識別性能ではありません。

デフォルトは [ローカルモニター](http://127.0.0.1:8090/)。別ポートは `-Port 8091`、別Pythonは `-ForestPython 'C:\path\to\python.exe'` で指定します。Ctrl+Cでモニターと子ワーカーを停止します。PCをスリープさせると学習は継続できません。

画像を用意したら次のように指定します。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\ml\start-local.ps1 -DatasetPath 'C:\Users\178ka\Documents\FOREST-DATA\fire-smoke-v1'
```

ローカル実行も本物の学習です。既存VPSのGo APIやPostgreSQLを立ち上げる必要はありません。

## データセットの置き方

```text
fire-smoke-v1/
  train/
    normal/   # 通常の森林画像
    fire/     # 炎を確認できる画像
    smoke/    # 煙を確認できる画像
  val/
    normal/
    fire/
    smoke/
```

- JPG、PNG、WebPに対応。各クラスに学習用と検証用が最低1枚ずつ必要です。これは動作条件であり、性能を得るための十分な枚数ではありません。
- 同一画像の重複をSHA-256で検出し、混入があるデータセットでは学習を受け付けません。似た連続フレームまでは判別できないため、同じ動画・場所・撮影日の画像は同じ側にまとめ、別の現場を検証用へ分けてください。
- 火と煙が同時に写る画像などは、人が一貫したルールでラベルを付けてください。3クラスは排他的です。両方を独立して判定する多ラベル分類は今後の拡張です。
- 雲・霧・夕焼けなど紛らわしい通常画像も含め、利用許諾を確認した画像を使用してください。
- 登録時と学習開始時の指紋を照合し、画像が変わった場合は失敗として表示します。学習中のデータ変更も検出します。
- 画像を読み込めないなどのエラーは履歴とログに残ります。画像そのものはPCに置いたままです。

## VPS側へ追加する

既存の未コミット変更、特にローカル公開ポートの設定を保ったまま、コードを取り込んでください。`compose.yaml` はこの機能では変更していません。

1. VPSの `.env.ml` に十分長く**異なる**値を設定します。各値は `python3 -c 'import secrets; print(secrets.token_urlsafe(32))'` などで生成できます。既存の `.env` は変更しません。`.env.ml` はモード600にしてコミットしません。

```dotenv
FOREST_ML_TOKEN=monitor用のランダムな値を設定
FOREST_ML_WORKER_TOKEN=worker用の別のランダムな値を設定
```

2. リポジトリルートで起動します。

```bash
docker compose --env-file .env --env-file .env.ml -f compose.yaml -f compose.ml.yaml build ml
docker compose --env-file .env --env-file .env.ml -f compose.yaml -f compose.ml.yaml up -d --no-deps ml api web
```

3. PCから下記のSSH方式で起動します。紹介サイトの `index.html` と管理画面の `monitor.html` は引き続き別です。

GPU学習はVPSで行いません。追加サービスは標準PythonとSQLiteだけで依頼・進捗・結果を永続化します。SQLiteとモデルはDockerの `ml-state` ボリュームに保存されます。`docker compose down -v` は学習履歴も削除するため使わないでください。

通信経路：`管理画面 → /api/ml/ → nginx → Go /ml/ → Python受付 → PCワーカー`。MLサービスのホストポートは公開しません。既存のlocalhostポート設定やアクセス制限を維持し、PCからはSSH転送・Tailscale等のプライベート経路、またはHTTPSを使ってください。認証キー付きHTTPを公衆ネットワークへ直接公開しないでください。

## PCワーカーをVPSへ接続する

### 通常は既存のSSH認証で接続

VPSの配置先が `/home/ubuntu/lab/forest_dcon2027`、SSH設定名が `my-vps` の場合、PCのリポジトリルートから次でモニター・SSH転送・GPUワーカーを起動できます。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\ml\start-vps.ps1
```

[VPSモニターの入口](http://127.0.0.1:18790/#training) が開きます。認証キーの入力・コピーは不要です。必要なら `-VpsHost`、`-LocalPort`、`-DatasetPath`、`-ForestPython` を指定します。画像はデフォルトでPCの `ml/datasets/fire-smoke-v1/` へ入れます。Ctrl+Cでこのワーカーと、この起動スクリプトが開いたSSH転送を停止します。

`forest_ml.ssh_bridge` はVPSの `127.0.0.1:18090` だけで待ち受けます。秘密の認証キーはVPSの `.env.ml` に保持し、PCへ返しません。SSH転送を通ったリクエストにVPS内で認証ヘッダーを付けます。PCが使う `ssh-session` の文字列は秘密ではなく、他サイトからの単純なフォーム送信を区別するためのマーカーです。HTTP以外のSSH認証がアクセスの境界になります。この入口を `0.0.0.0` へ公開したり、外部へ転送したりしないでください。

スクリプトはVPSのユーザーサービス `forest-ml-private-ssh` を必要に応じて起動します。このサービスはトランジェントなのでVPS再起動後は再度スクリプトを実行します。サービスを停止する場合はVPSで `systemctl --user stop forest-ml-private-ssh`。配置先が異なる場合は `start-vps.ps1` の固定パスを合わせてください。

### 明示的なキー認証を使う場合

SSH転送などでVPSのWebポートをPCの `18081` に転送した例です。サーバーURLは環境に合わせます。認証キーはURLやコマンド引数へ含めません。

```powershell
$workerSecret = Read-Host 'VPSのFOREST_ML_WORKER_TOKEN' -AsSecureString
$env:FOREST_ML_WORKER_TOKEN = [System.Net.NetworkCredential]::new('', $workerSecret).Password
Set-Location .\ml
& "$env:USERPROFILE\miniconda3\envs\forest_gpu\python.exe" -m forest_ml.worker `
  --server http://127.0.0.1:18081/api/ml `
  --worker-id forest-gpu-pc `
  --dataset 'fire-smoke-v1=C:\Users\178ka\Documents\FOREST-DATA\fire-smoke-v1'
```

ワーカーは5秒ごとに依頼を確認し、実行中は4秒ごとに生存を通知します。同じPCは1ジョブずつ実行します。90秒以上通知がない実行中ジョブは失敗になり、自動再実行はしません。停止ボタンの要求はバッチ境界等で反映します。OSやCUDA処理で完全停止したプロセスを遠隔で強制終了する機能ではありません。別ワーカーが処理中の依頼を奪うことはできません。

このモニターは既存のSSH方式 `forest_gpu_worker.py` とは独立して起動します。既存ワーカーを上書き・停止しません。GPUを同時に使わせないよう、利用するワーカーを選んでください。外部から任意のPython・シェルコマンドを送る機能はありません。

## モデルを試す

完了した履歴から `model.pth` と `result.json` をダウンロードできます。転送時はSHA-256を照合し、`result.json` にモデルのハッシュ・画像指紋・PyTorch/CUDA・学習履歴を記録します。モデルは保存後に `weights_only=True` で再読込を検証します。

```powershell
# ml/ 内で実行。モデルは自分が生成したものを使用します。
& "$env:USERPROFILE\miniconda3\envs\forest_gpu\python.exe" -m forest_ml.predict `
  --model 'C:\path\to\model.pth' --image 'C:\path\to\image.jpg'
```

予測クラスと3クラスの確率を返します。正解率だけで判断せず、火災や煙を通常に見逃した件数を分類表で確認してください。検証セットを設定選びに繰り返し使った後は、独立したテストセットで最終評価してください。

## 開発とテスト

```bash
cd ml
python -m unittest discover -s tests -v
```

画像学習・モデル再読込・推論・結果転送・停止を実際のPyTorchで確認する場合：

```powershell
$env:FOREST_ML_INTEGRATION='1'
$env:FOREST_ML_TEST_DEVICE='cuda' # GPUのない開発PCではcpu
python -m unittest discover -s tests -v
```

生成した画像フィクスチャを使用するため、このテストは実際の火災・煙への性能を示しません。Go側の中継テストはリポジトリルートで `go test ./go/cmd/api`。

依頼と結果のJSON境界を保ち、将来のPostgreSQL保存、別モデル、Jetson向け書き出しへ置き換えられる構成です。初期版のモデル選択は `forest_cnn_v1` 固定です。認証・画像・モデル・学習履歴・ローカル状態はGitへ含めません。
