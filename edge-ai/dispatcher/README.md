# FOREST GPU Dispatcher v1

FOREST Edge AI の学習ジョブを VPS から GPU 搭載 PC に配送し、
学習成果物を検証して VPS に返却するための仕組み。

## Purpose

RTX 5050 搭載 PC を FOREST の学習・開発マシンとして利用する。

最終システムでは Jetson 等が現場で推論を担当し、
GPU Dispatcher はモデルの学習・更新を行う開発基盤として位置づける。

## Architecture

VPS
  |
  | FOREST_EDGE_TRAIN job
  v
PC Worker
  |
  | verify Git commit / repository state
  v
edge-ai/dispatcher/run_job.py
  |
  v
edge-ai/src/train.py
  |
  | CUDA
  v
NVIDIA GPU
  |
  v
model.pth
metadata.json
result.json
training.log
  |
  | SCP
  v
VPS
  |
  v
artifact verification
  |
  v
COMPLETED

## Job v1

FOREST training jobs use:

```json
{
  "job_type": "FOREST_EDGE_TRAIN",
  "git_commit": "<40-character Git commit>",
  "dataset_id": "forest-smoke-v0",
  "epochs": 3,
  "batch_size": 8,
  "image_size": 224,
  "pretrained": false
}