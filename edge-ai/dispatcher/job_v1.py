from dataclasses import asdict, dataclass
import argparse
import json


@dataclass(frozen=True)
class ForestEdgeTrainJob:
    job_type: str
    git_commit: str
    dataset_id: str
    epochs: int
    batch_size: int
    image_size: int
    pretrained: bool

    def validate(self) -> None:
        if self.job_type != "FOREST_EDGE_TRAIN":
            raise ValueError("unsupported job_type")
        if not self.git_commit:
            raise ValueError("git_commit is required")
        if not self.dataset_id:
            raise ValueError("dataset_id is required")
        if self.epochs < 1:
            raise ValueError("epochs must be at least 1")
        if self.batch_size < 1:
            raise ValueError("batch_size must be at least 1")
        if self.image_size < 32:
            raise ValueError("image_size must be at least 32")

    def to_json(self) -> str:
        self.validate()
        return json.dumps(asdict(self), indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="Create a FOREST Edge AI training job"
    )
    parser.add_argument("--git-commit", required=True)
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--image-size", type=int, default=224)
    parser.add_argument("--pretrained", action="store_true")
    args = parser.parse_args()

    job = ForestEdgeTrainJob(
        job_type="FOREST_EDGE_TRAIN",
        git_commit=args.git_commit,
        dataset_id=args.dataset_id,
        epochs=args.epochs,
        batch_size=args.batch_size,
        image_size=args.image_size,
        pretrained=args.pretrained,
    )

    print(job.to_json())


if __name__ == "__main__":
    main()