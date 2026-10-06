from dataclasses import asdict, dataclass
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
    job = ForestEdgeTrainJob(
        job_type="FOREST_EDGE_TRAIN",
        git_commit="2b40693",
        dataset_id="forest-smoke-v0",
        epochs=3,
        batch_size=8,
        image_size=224,
        pretrained=False,
    )

    print(job.to_json())


if __name__ == "__main__":
    main()