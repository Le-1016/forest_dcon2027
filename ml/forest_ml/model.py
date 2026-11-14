def build_model():
    from torch import nn
    return nn.Sequential(
        nn.Conv2d(3,16,3,padding=1),nn.ReLU(),nn.MaxPool2d(2),
        nn.Conv2d(16,32,3,padding=1),nn.ReLU(),nn.MaxPool2d(2),
        nn.Conv2d(32,64,3,padding=1),nn.ReLU(),nn.AdaptiveAvgPool2d(1),
        nn.Flatten(),nn.Linear(64,3),
    )
