"""Trains Tector's AI-image classifier (logistic regression on CLIP features) and reports
held-out accuracy per image source.

Usage: python train_classifier.py <train.npz> <test.npz> <out_head.npz>
"""
import collections
import sys

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score


def normalize(X):
    return X / np.linalg.norm(X, axis=1, keepdims=True)


def source_of(name):
    return name.split("__")[1] if "__" in name else "?"


def main():
    train, test, out = np.load(sys.argv[1]), np.load(sys.argv[2]), sys.argv[3]
    Xtr, ytr = normalize(train["X"]), train["y"]
    Xte, yte = normalize(test["X"]), test["y"]

    best_c, best_score = None, -1
    for c in (0.3, 1, 3, 10, 30):
        clf = LogisticRegression(C=c, max_iter=5000, class_weight="balanced")
        score = cross_val_score(clf, Xtr, ytr, cv=5).mean()
        print(f"C={c:<5} cross-val accuracy {score:.3f}")
        if score > best_score:
            best_c, best_score = c, score

    clf = LogisticRegression(C=best_c, max_iter=5000, class_weight="balanced").fit(Xtr, ytr)
    probs = clf.predict_proba(Xte)[:, 1]
    pred = probs >= 0.5
    print(f"\nHeld-out accuracy: {(pred == yte).mean():.3f}  (C={best_c})")
    print(f"  real images wrongly flagged: {(pred & (yte == 0)).sum()}/{(yte == 0).sum()}")
    print(f"  AI images caught:            {(pred & (yte == 1)).sum()}/{(yte == 1).sum()}")
    by_source = collections.defaultdict(list)
    for name, p, y in zip(test["names"], pred, yte):
        by_source[source_of(str(name))].append(p == y)
    for src, hits in sorted(by_source.items()):
        print(f"  {src:16s} {sum(hits)}/{len(hits)}")

    np.savez(out, coef=clf.coef_[0].astype(np.float32), intercept=np.float32(clf.intercept_[0]))
    np.save(out.replace(".npz", "_test_probs.npy"), probs)
    print("saved", out)


if __name__ == "__main__":
    main()
