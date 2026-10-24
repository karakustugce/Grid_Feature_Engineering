"""Chronological split, persistence baseline, ridge, and a small MLP.

The model predicts the next-session log return r = log(C_{t+1}/C_t) and
reconstructs the close as C_t * exp(r_hat). Price levels are non-stationary
(an 80/20 split means test prices sit outside the training range); returns are
roughly stationary, so the network learns *changes*, and dollar MAE is still
reported on the reconstructed close.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer


# ---------------------------------------------------------------- splitting
def chrono_split(df: pd.DataFrame, test_frac: float = 0.20, embargo: int = 1):
    """Earliest 80% for development, latest 20% for the final test. No shuffling."""
    n = len(df)
    cut = int(np.floor(n * (1 - test_frac)))
    dev = df.iloc[: cut - embargo]
    test = df.iloc[cut:]
    return dev, test


def expanding_folds(n: int, n_folds: int = 5, min_train: float = 0.5):
    """Walk-forward validation inside the development set."""
    start = int(n * min_train)
    edges = np.linspace(start, n, n_folds + 1, dtype=int)
    for a, b in zip(edges[:-1], edges[1:]):
        yield np.arange(0, a), np.arange(a, b)


# ---------------------------------------------------------------- metrics
def evaluate(close_t: pd.Series, y_close: pd.Series, r_hat: np.ndarray, label: str) -> dict:
    pred = close_t.values * np.exp(r_hat)
    err = pred - y_close.values
    true_dir = np.sign(y_close.values - close_t.values)
    pred_dir = np.sign(r_hat)
    nz = pred_dir != 0
    return {
        "model": label,
        "mae_usd": float(np.mean(np.abs(err))),
        "rmse_usd": float(np.sqrt(np.mean(err ** 2))),
        "dir_acc": float(np.mean(pred_dir[nz] == true_dir[nz])) if nz.any() else np.nan,
        "n": int(len(err)),
    }


# ---------------------------------------------------------------- models
def fit_ridge(X: pd.DataFrame, y: pd.Series, alphas=(0.1, 1, 10, 100, 1000), n_folds: int = 5):
    """Pick alpha by walk-forward MAE on returns, then refit on all dev rows."""
    best, best_mae = None, np.inf
    for a in alphas:
        maes = []
        for tr, va in expanding_folds(len(X), n_folds):
            m = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), Ridge(alpha=a))
            m.fit(X.iloc[tr], y.iloc[tr])
            maes.append(np.mean(np.abs(m.predict(X.iloc[va]) - y.iloc[va])))
        if np.mean(maes) < best_mae:
            best, best_mae = a, float(np.mean(maes))
    model = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), Ridge(alpha=best)).fit(X, y)
    return model, {"alpha": best, "cv_mae_ret": best_mae}


@dataclass
class MLPConfig:
    hidden: int = 16
    dropout: float = 0.2
    lr: float = 1e-3          # small steps
    weight_decay: float = 1e-3
    max_epochs: int = 500
    patience: int = 25        # stop when validation stops improving
    batch_size: int = 64
    val_frac: float = 0.15    # last 15% of dev, chronologically
    loss: str = "huber"       # 'l1' targets MAE directly; huber is smoother near 0
    seed: int = 0
    history: list = field(default_factory=list)


def fit_mlp(X: pd.DataFrame, y: pd.Series, cfg: MLPConfig = MLPConfig()):
    import torch
    from torch import nn

    torch.manual_seed(cfg.seed)
    np.random.seed(cfg.seed)
    n_val = max(int(len(X) * cfg.val_frac), 20)
    pre = make_pipeline(SimpleImputer(strategy="median"), StandardScaler())
    Xtr_np = pre.fit_transform(X.iloc[:-n_val])           # scaler fitted on train part only
    Xva_np = pre.transform(X.iloc[-n_val:])
    y_scale = float(y.iloc[:-n_val].std())                 # returns are ~0.01; rescale for stable gradients
    ytr = torch.tensor(y.iloc[:-n_val].values / y_scale, dtype=torch.float32).unsqueeze(1)
    yva = torch.tensor(y.iloc[-n_val:].values / y_scale, dtype=torch.float32).unsqueeze(1)
    Xtr = torch.tensor(Xtr_np, dtype=torch.float32)
    Xva = torch.tensor(Xva_np, dtype=torch.float32)

    net = nn.Sequential(nn.Linear(X.shape[1], cfg.hidden), nn.Tanh(), nn.Dropout(cfg.dropout), nn.Linear(cfg.hidden, 1))
    nn.init.zeros_(net[-1].weight); nn.init.zeros_(net[-1].bias)   # start AT the persistence baseline
    opt = torch.optim.AdamW(net.parameters(), lr=cfg.lr, weight_decay=cfg.weight_decay)
    lossf = nn.L1Loss() if cfg.loss == "l1" else nn.HuberLoss(delta=1.0)

    best_state, best_val, bad = None, np.inf, 0
    cfg.history = []
    for epoch in range(cfg.max_epochs):
        net.train()
        perm = torch.randperm(len(Xtr))  # shuffling *within* the training block is fine
        for i in range(0, len(Xtr), cfg.batch_size):
            b = perm[i : i + cfg.batch_size]
            opt.zero_grad()
            loss = lossf(net(Xtr[b]), ytr[b])
            loss.backward()
            opt.step()
        net.eval()
        with torch.no_grad():
            tr_mae = float((net(Xtr) - ytr).abs().mean()) * y_scale
            va_mae = float((net(Xva) - yva).abs().mean()) * y_scale
        cfg.history.append({"epoch": epoch, "train_mae_ret": tr_mae, "val_mae_ret": va_mae})
        if va_mae < best_val - 1e-7:
            best_val, bad = va_mae, 0
            best_state = {k: v.clone() for k, v in net.state_dict().items()}
        else:
            bad += 1
            if bad >= cfg.patience:
                break
    net.load_state_dict(best_state)
    net.eval()

    def predict(Xn: pd.DataFrame) -> np.ndarray:
        with torch.no_grad():
            return net(torch.tensor(pre.transform(Xn), dtype=torch.float32)).squeeze(1).numpy() * y_scale

    return predict, {"best_val_mae_ret": best_val, "epochs_run": len(cfg.history), "history": cfg.history}


# ---------------------------------------------------------------- ablation
def run_ablation(panel: pd.DataFrame, groups: dict[str, list[str]], order: list[str], use_mlp: bool = True):
    """Add feature families one at a time; score each on the untouched test 20%."""
    panel = panel.dropna(subset=["y_logret", "y_close"])
    dev, test = chrono_split(panel)
    rows = [evaluate(test["aapl_close"], test["y_close"], np.zeros(len(test)), "persistence")]
    preds = {"persistence": test["aapl_close"].values.copy()}
    to_close = lambda r_hat: test["aapl_close"].values * np.exp(r_hat)  # noqa: E731
    cols: list[str] = []
    for g in order:
        cols = cols + [c for c in groups[g] if c in panel and c not in cols]
        ridge, info = fit_ridge(dev[cols], dev["y_logret"])
        r_hat = ridge.predict(test[cols])
        preds[f"ridge +{g}"] = to_close(r_hat)
        r = evaluate(test["aapl_close"], test["y_close"], r_hat, f"ridge +{g}")
        r.update(n_features=len(cols), alpha=info["alpha"])
        rows.append(r)
        if use_mlp and len(dev) >= 80:   # too few rows for a validation split otherwise
            pred, minfo = fit_mlp(dev[cols], dev["y_logret"])
            r_hat = pred(test[cols])
            preds[f"mlp +{g}"] = to_close(r_hat)
            r = evaluate(test["aapl_close"], test["y_close"], r_hat, f"mlp +{g}")
            r.update(n_features=len(cols), epochs=minfo["epochs_run"])
            rows.append(r)
    res = pd.DataFrame(rows)
    base = res.loc[0, "mae_usd"]
    res["mae_vs_persistence_pct"] = (res["mae_usd"] / base - 1) * 100
    res.attrs["predictions"] = pd.DataFrame(preds, index=test.index).assign(actual=test["y_close"].values)
    return res, dev, test
