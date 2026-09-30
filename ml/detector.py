"""Vessel-presence detector: small fully convolutional CNN vs. a CA-CFAR baseline.

Task: given a 1.6 km Sentinel-1 chip (VV, VH in dB), is there a vessel that
GFW detected in it, and where? The network outputs a heatmap at 1/4 resolution;
chip presence is the heatmap maximum (multiple-instance style), and the peak
gives the position. It is trained only on chip-level labels.

Evaluation is on held-out *scenes* (no chip from a test scene is seen in
training). The reference is GFW's own SAR detections, so these numbers measure
agreement with GFW's detector, not ground truth.

Usage: python -m ml.detector train | eval
"""

import argparse
import json
import time

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from sklearn.metrics import average_precision_score, precision_recall_curve, roc_auc_score

from ml import CACHE, cfar, dataset, s1

MODEL = CACHE / "models" / "detector.pt"
REPORT = CACHE / "reports" / "detector.json"
SEED = 7


def load_chip(name):
    with np.load(dataset.CHIPS / f"{name}.npz") as z:
        return z["chip"].astype(np.float32)


def normalise(chip):
    db = s1.to_db(chip)                       # (2, H, W) in [-30, 10]
    return ((db + 20.0) / 10.0).astype(np.float32)


class Chips(torch.utils.data.Dataset):
    def __init__(self, df, augment=False):
        self.df = df.reset_index(drop=True)
        self.augment = augment
        self.cache = {}

    def __len__(self):
        return len(self.df)

    def __getitem__(self, i):
        r = self.df.iloc[i]
        if r.chip not in self.cache:  # float16 halves memory; the machine has ~16 GB shared
            self.cache[r.chip] = normalise(load_chip(r.chip)).astype(np.float16)
        x = self.cache[r.chip].astype(np.float32)
        if self.augment:  # SAR geometry is not rotation-invariant, but flips keep look direction pairs plausible
            if np.random.rand() < 0.5:
                x = x[:, :, ::-1]
            if np.random.rand() < 0.5:
                x = x[:, ::-1, :]
        return torch.from_numpy(np.ascontiguousarray(x)), torch.tensor(float(r.label))


class Net(nn.Module):
    """~120k parameters; fits comfortably on a 4 GB GPU."""

    def __init__(self):
        super().__init__()

        def block(i, o):
            return nn.Sequential(nn.Conv2d(i, o, 3, padding=1), nn.BatchNorm2d(o), nn.ReLU(inplace=True),
                                 nn.Conv2d(o, o, 3, padding=1), nn.BatchNorm2d(o), nn.ReLU(inplace=True))

        self.b1, self.b2, self.b3 = block(2, 16), block(16, 32), block(32, 64)
        self.head = nn.Conv2d(64, 1, 1)

    def heatmap(self, x):
        x = F.max_pool2d(self.b1(x), 2)
        x = F.max_pool2d(self.b2(x), 2)
        return self.head(self.b3(x))[:, 0]   # (N, H/4, W/4) logits

    def forward(self, x):
        return self.heatmap(x).flatten(1).max(1).values


def splits():
    df = dataset.load()
    return {s: df[df.split == s] for s in ("train", "val", "test")}


def train(epochs=25, batch=64, lr=2e-3):
    torch.manual_seed(SEED)
    np.random.seed(SEED)
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    sp = splits()
    tl = torch.utils.data.DataLoader(Chips(sp["train"], augment=True), batch_size=batch, shuffle=True)
    vl = torch.utils.data.DataLoader(Chips(sp["val"]), batch_size=256)
    net = Net().to(dev)
    opt = torch.optim.AdamW(net.parameters(), lr=lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, epochs)
    best, t0 = -1.0, time.time()
    for ep in range(epochs):
        net.train()
        for x, y in tl:
            x, y = x.to(dev), y.to(dev)
            loss = F.binary_cross_entropy_with_logits(net(x), y)
            opt.zero_grad()
            loss.backward()
            opt.step()
        sched.step()
        ys, ps = predict(net, vl, dev)
        ap = average_precision_score(ys, ps)
        if ap > best:
            best = ap
            MODEL.parent.mkdir(parents=True, exist_ok=True)
            torch.save(net.state_dict(), MODEL)
        print(f"epoch {ep + 1:2d}  loss {loss.item():.3f}  val PR-AUC {ap:.3f}")
    print(f"best val PR-AUC {best:.3f}; {time.time() - t0:.0f}s on {dev}")


@torch.no_grad()
def predict(net, loader, dev):
    net.eval()
    ys, ps = [], []
    for x, y in loader:
        ps.append(torch.sigmoid(net(x.to(dev))).cpu().numpy())
        ys.append(y.numpy())
    return np.concatenate(ys), np.concatenate(ps)


def load_model(dev="cpu"):
    net = Net()
    net.load_state_dict(torch.load(MODEL, map_location=dev, weights_only=True))
    return net.to(dev).eval()


@torch.no_grad()
def peak(net, chip, dev="cpu"):
    """(probability, row, col) of the strongest response, in chip pixels."""
    x = torch.from_numpy(normalise(chip))[None].to(dev)
    h = net.heatmap(x)[0]
    i = int(torch.argmax(h))
    r, c = divmod(i, h.shape[1])
    return float(torch.sigmoid(h.flatten()[i])), r * 4 + 2, c * 4 + 2


def at_threshold(ys, ps, thr):
    pred = ps >= thr
    tp, fp, fn = int((pred & (ys == 1)).sum()), int((pred & (ys == 0)).sum()), int((~pred & (ys == 1)).sum())
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return {"threshold": float(thr), "precision": p, "recall": r, "f1": 2 * p * r / (p + r) if p + r else 0.0,
            "tp": tp, "fp": fp, "fn": fn}


def best_f1_threshold(ys, ps):
    p, r, t = precision_recall_curve(ys, ps)
    f1 = 2 * p * r / np.maximum(p + r, 1e-9)
    return float(t[np.argmax(f1[:-1])])


def bootstrap(ys, ps, fn, n=1000, seed=SEED):
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(n):
        i = rng.integers(0, len(ys), len(ys))
        if ys[i].min() == ys[i].max():
            continue
        vals.append(fn(ys[i], ps[i]))
    return [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))]


def evaluate():
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    sp = splits()
    net = load_model(dev)
    out = {"reference": "GFW public-global-sar-presence detections (agreement, not ground truth)",
           "split": "by Sentinel-1 scene (70/15/15 hash of scene id)",
           "counts": {s: {"chips": int(len(d)), "positive": int(d.label.sum()), "scenes": int(d.scene.nunique())}
                      for s, d in sp.items()}}

    # Thresholds are chosen on validation, then applied unchanged to test.
    scores = {}
    for name in ("val", "test"):
        d = sp[name]
        ys = d.label.to_numpy()
        _, cnn = predict(net, torch.utils.data.DataLoader(Chips(d), batch_size=256), dev)
        cf = np.array([cfar.chip_score(load_chip(c)) for c in d.chip])
        scores[name] = (ys, cnn, cf)
    thr = {"cnn": best_f1_threshold(scores["val"][0], scores["val"][1]),
           "cfar": best_f1_threshold(scores["val"][0], scores["val"][2])}
    ys, cnn, cf = scores["test"]
    for name, ps in (("cnn", cnn), ("cfar", cf)):
        out[name] = {
            "pr_auc": float(average_precision_score(ys, ps)),
            "pr_auc_ci95": bootstrap(ys, ps, average_precision_score),
            "roc_auc": float(roc_auc_score(ys, ps)),
            "at_val_threshold": at_threshold(ys, ps, thr[name]),
        }
    d = sp["test"].assign(cnn=cnn, cfar=cf)
    out["by_group"] = {}
    for g, sub in (("matched", d[(d.label == 0) | d.matched]), ("unmatched", d[(d.label == 0) | ~d.matched]),
                   ("our_vessels", d[(d.label == 0) | d.ours])):
        if sub.label.sum() == 0:
            continue
        out["by_group"][g] = {m: at_threshold(sub.label.to_numpy(), sub[m].to_numpy(), thr[m])["recall"]
                              for m in ("cnn", "cfar")}
    out["by_group"]["note"] = "recall on positives of each group at the validation threshold"

    # Localisation: CNN peak should fall inside the ~1 km GFW cell (within 800 m of its centre).
    pos = d[d.label == 1]
    err = []
    for r in pos.itertuples():
        _, pr, pc = peak(net, load_chip(r.chip), dev)
        err.append(10.0 * np.hypot(pr - s1.CHIP / 2, pc - s1.CHIP / 2))
    err = np.array(err)
    out["cnn"]["peak_within_800m_of_cell_centre"] = float((err <= 800).mean())
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["train", "eval"])
    ap.add_argument("--epochs", type=int, default=25)
    a = ap.parse_args()
    train(a.epochs) if a.cmd == "train" else evaluate()
