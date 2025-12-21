import torch
from Modules.IDrecognition.jersey_recognizer import JerseyClassifier


def test_jersey_forward():
    model = JerseyClassifier(num_classes=3)
    model.eval()
    # create a batch of 2 RGB images 3x64x64
    x = torch.randn(2, 3, 64, 64)
    with torch.no_grad():
        out = model(x)
    assert out.shape == (2, 3)
