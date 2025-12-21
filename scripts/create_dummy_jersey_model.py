"""Create a dummy pre-trained jersey model for testing.

This script creates a small 2-class JerseyClassifier and saves it as a .pth file.
It's intended for testing the model loading pipeline before real training data is available.
"""
import sys
import warnings
import torch

# Suppress deprecation warnings from torchvision
warnings.filterwarnings('ignore', category=DeprecationWarning)

sys.path.insert(0, '.')
from Modules.IDrecognition.jersey_recognizer import JerseyClassifier, save_model


def create_dummy_model(output_path='models/jersey_resnet18_cpu.pth'):
    # Create a simple 2-class classifier (e.g., team A vs team B)
    model = JerseyClassifier(num_classes=2, pretrained=False)
    model.eval()

    # Save it
    save_model(model, output_path)
    print(f"Dummy model saved to {output_path}")
    print(f"Model has {sum(p.numel() for p in model.parameters())} parameters")


if __name__ == '__main__':
    create_dummy_model()
