# FOREST Model Version v1

## Purpose

Create and verify a model_manifest.json containing:
- Model ID, version, and Git commit
- Dataset ID, task, architecture, and classes
- Training parameters
- SHA-256 hashes of model and metadata
- Optional Dispatcher job and evaluation artifacts

## Create

Run from the repository root:

    python3 edge-ai/dispatcher/model_version.py create \
      --model-id forest-edge-dispatch-smoke \
      --version 0.1.0 \
      --git-commit FULL_40_CHARACTER_GIT_SHA \
      --model /path/to/model.pth \
      --metadata /path/to/metadata.json \
      --job /path/to/job.json \
      --output /path/to/model_manifest.json

The --job argument is optional for newer metadata.

All supplied artifacts and the output manifest must be
in the same directory.

## Verify

    python3 edge-ai/dispatcher/model_version.py verify \
      --manifest /path/to/model_manifest.json

## Legacy compatibility

Older Dispatcher metadata may omit dataset_id and dataset_task.

With --job, the tool checks the completed job, Git commit,
model and metadata hashes, dataset ID, and training parameters.

Missing dataset_id is obtained from the Dispatcher job.
Missing dataset_task defaults to image_classification.

The provenance field identifies these sources.
The legacy dataset_task default is a compatibility rule,
not a value originally recorded during training.

## Limitations

SHA-256 detects changes but does not prove authorship.
The Git commit field alone does not prove training provenance.
Model accuracy must be evaluated separately.
This is a local manifest, not a model registry.
