"""Simple jersey recognition classifier (PyTorch).

This module provides a lightweight ResNet18-based classifier and a Dataset
stub that expects images organized by class in folders. It's intended as a
starting point for building a kit-recognition CNN.
"""
from typing import Optional
import warnings
import torch
import torch.nn as nn
from torchvision import models, transforms
from torch.utils.data import Dataset
from PIL import Image
import os
import numpy as np

# Suppress torchvision deprecation warnings about pretrained parameter
warnings.filterwarnings('ignore', category=DeprecationWarning, module='torchvision')


class JerseyDataset(Dataset):
    """Minimal dataset reading image files organized as:
    root/class_x/*.jpg
    root/class_y/*.jpg
    """

    def __init__(self, root_dir: str, transform: Optional[transforms.Compose] = None):
        self.root_dir = root_dir
        self.transform = transform or transforms.Compose([
            transforms.Resize((64, 64)),
            transforms.ToTensor()
        ])
        self.samples = []  # list of (path, label)
        classes = sorted([d for d in os.listdir(root_dir) if os.path.isdir(os.path.join(root_dir, d))])
        self.class_to_idx = {c: i for i, c in enumerate(classes)}
        for c in classes:
            p = os.path.join(root_dir, c)
            for fn in os.listdir(p):
                if fn.lower().endswith(('.jpg', '.png', '.jpeg')):
                    self.samples.append((os.path.join(p, fn), self.class_to_idx[c]))

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        path, label = self.samples[idx]
        img = Image.open(path).convert('RGB')
        img = self.transform(img)
        return img, label


class JerseyClassifier(nn.Module):
    def __init__(self, num_classes: int = 2, pretrained: bool = False):
        super().__init__()
        # use a small ResNet18 backbone
        # use weights=None instead of deprecated pretrained parameter
        self.backbone = models.resnet18(weights=None)
        # adapt for small input size if desired
        in_features = self.backbone.fc.in_features
        self.backbone.fc = nn.Linear(in_features, num_classes)

    def forward(self, x):
        return self.backbone(x)


def load_model(path: str, device: str = 'cpu') -> nn.Module:
    model = torch.load(path, map_location=device, weights_only=False)
    model.eval()
    return model


def save_model(model: nn.Module, path: str):
    torch.save(model, path)


def predict_from_bgr(model: nn.Module, bgr_img, class_names=None, device: str = 'cpu'):
    """Predict jersey class from a BGR numpy crop.

    Returns class index (int) or class name if `class_names` provided.
    Safe: returns None on any failure.
    """
    try:
        # convert BGR numpy array to PIL RGB
        if isinstance(bgr_img, np.ndarray):
            img = Image.fromarray(bgr_img[:, :, ::-1])
        else:
            img = bgr_img
        tf = transforms.Compose([
            transforms.Resize((64, 64)),
            transforms.ToTensor()
        ])
        x = tf(img).unsqueeze(0).to(device)
        model = model.to(device)
        model.eval()
        with torch.no_grad():
            logits = model(x)
            pred = int(torch.argmax(logits, dim=1).item())
        if class_names and pred < len(class_names):
            return class_names[pred]
        return pred
    except Exception:
        return None
