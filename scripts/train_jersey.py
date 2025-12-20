"""Training script stub for the JerseyClassifier.

This is a minimal training loop intended as a starting point. It will
train for a few epochs on a dataset organized by class under `data_root`.
"""
import argparse
import torch
from torch import optim, nn
from torch.utils.data import DataLoader
from Modules.IDrecognition.jersey_recognizer import JerseyDataset, JerseyClassifier


def train(data_root, epochs=2, batch_size=16, lr=1e-3, device='cpu'):
    ds = JerseyDataset(data_root)
    num_classes = len(ds.class_to_idx)
    dl = DataLoader(ds, batch_size=batch_size, shuffle=True)

    model = JerseyClassifier(num_classes=num_classes)
    model.to(device)
    opt = optim.Adam(model.parameters(), lr=lr)
    crit = nn.CrossEntropyLoss()

    model.train()
    for ep in range(epochs):
        total_loss = 0.0
        for x, y in dl:
            x = x.to(device)
            y = y.to(device)
            opt.zero_grad()
            logits = model(x)
            loss = crit(logits, y)
            loss.backward()
            opt.step()
            total_loss += loss.item()
        print(f"Epoch {ep+1}/{epochs} loss={total_loss/len(dl):.4f}")

    return model


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', required=True, help='Path to dataset root')
    parser.add_argument('--epochs', type=int, default=2)
    parser.add_argument('--batch', type=int, default=16)
    args = parser.parse_args()
    train(args.data, epochs=args.epochs, batch_size=args.batch)
