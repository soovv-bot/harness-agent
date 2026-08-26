"""Judge 人工校准基线（ROADMAP M3 ③）。

两步闭环：
1) 抽样生成人工标注模板（确定性 seed，分层覆盖正确/错误/无 answer）：
     python -m scripts.analysis.judge_calibration sample \
         --input results/cluster_run_seed123_k100.json --n 30 --seed 20260825 \
         --out results/human_calibration_seed_20260825.jsonl
2) 标注后计算一致性（accuracy / Cohen's kappa / 混淆矩阵）：
     python -m scripts.analysis.judge_calibration agreement \
         --labels results/human_calibration_seed_20260825.jsonl

标注格式：sample 产出的 jsonl，每行追加 "human_correct": true/false 即可。
依赖纯 stdlib + stats_utils，可复算、可审计。
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

_HERE = Path(__file__).resolve().parent.parent.parent
import sys as _sys
if str(_HERE) not in _sys.path:
    _sys.path.insert(0, str(_HERE))

import utils.stats_utils as su

DEFAULT_SEED = 20260825


def _bucket(r: Dict[str, Any]) -> str:
    if r.get("grader_error_type"):
        return "grader_error"
    if r.get("is_correct") is True:
        return "correct"
    if r.get("is_correct") is False:
        return "incorrect"
    return "ungraded"


def sample_for_labeling(
    results: List[Dict[str, Any]],
    n: int,
    seed: int = DEFAULT_SEED,
) -> List[Dict[str, Any]]:
    """确定性分层抽样：尽量均匀覆盖各 bucket，超出 bucket 容量时从其他桶补足。

    同一 (results, n, seed) 永远产出同一批样本 → 校准基线可复算。
    """
    rng = random.Random(seed)
    buckets: Dict[str, List[Dict[str, Any]]] = {}
    for r in results:
        buckets.setdefault(_bucket(r), []).append(r)
    for items in buckets.values():
        rng.shuffle(items)

    order = sorted(buckets)
    picked: List[Dict[str, Any]] = []
    quota = n // max(len(order), 1)
    leftover = n
    for b in order:
        take = min(quota, len(buckets[b]))
        picked.extend(buckets[b][:take])
        leftover -= take
    # 跨桶补足剩余名额（确定性顺序）
    pool = [r for b in order for r in buckets[b][quota:]]
    picked.extend(pool[:leftover])

    return [
        {
            "task_index": r.get("task_index"),
            "question_preview": r.get("question_preview") or r.get("question"),
            "correct_answer": r.get("correct_answer"),
            "extracted_answer": r.get("extracted_answer"),
            "judge_verdict": r.get("is_correct"),
            "judge_bucket": _bucket(r),
            "human_correct": None,
            "human_note": "",
        }
        for r in picked
    ]


def cohens_kappa(a: List[bool], b: List[bool]) -> Optional[float]:
    """Cohen's kappa：judge 与人工的二值一致性。样本不足返回 None。"""
    assert len(a) == len(b)
    if not a:
        return None
    agreed = sum(1 for x, y in zip(a, b) if x == y) / len(a)
    pa = sum(a) / len(a)
    pb = sum(b) / len(b)
    pe = pa * pb + (1 - pa) * (1 - pb)
    if pe >= 1.0:
        return None  # 退化：双方都全对/全错时 kappa 无定义
    return (agreed - pe) / (1 - pe)


def agreement_report(labeled: List[Dict[str, Any]]) -> Dict[str, Any]:
    """从带 human_correct 标注的样本计算 judge 校准基线。

    返回 dict：agreement、kappa、混淆矩阵 2x2、按桶分层 agreement，
    以及被 judge 错判的样本列表（供人工复检）。
    """
    ok = [
        x for x in labeled
        if isinstance(x.get("human_correct"), bool) and isinstance(x.get("judge_verdict"), bool)
    ]
    skipped = len(labeled) - len(ok)
    if not ok:
        return {"n_labeled": 0, "skipped": skipped, "error": "no labeled pairs"}

    judge = [x["judge_verdict"] for x in ok]
    human = [x["human_correct"] for x in ok]
    tp = sum(1 for j, h in zip(judge, human) if j and h)
    fp = sum(1 for j, h in zip(judge, human) if j and not h)
    fn = sum(1 for j, h in zip(judge, human) if not j and h)
    tn = sum(1 for j, h in zip(judge, human) if not j and not h)
    agree = tp + tn
    acc_ci = su.bootstrap_ci([1.0 if j == h else 0.0 for j, h in zip(judge, human)])
    report = {
        "n_labeled": len(ok),
        "skipped_unlabeled": skipped,
        "agreement": agree / len(ok),
        "agreement_ci95": [acc_ci["ci"]["low"], acc_ci["ci"]["high"]],
        "cohens_kappa": cohens_kappa(judge, human),
        "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        "by_bucket": _per_bucket(ok),
        "disagreements": [
            {
                "task_index": x["task_index"],
                "judge_verdict": x["judge_verdict"],
                "human_correct": x["human_correct"],
                "extracted_answer": x.get("extracted_answer"),
                "correct_answer": x.get("correct_answer"),
                "human_note": x.get("human_note", ""),
            }
            for x in ok if x["judge_verdict"] != x["human_correct"]
        ],
    }
    return report


def _per_bucket(labeled: List[Dict[str, Any]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for bucket, group in _groupby(labeled, lambda x: x.get("judge_bucket") or "unknown").items():
        n = len(group)
        ag = sum(1 for x in group if x["judge_verdict"] == x["human_correct"])
        out[bucket] = {"n": n, "agreement": ag / n if n else None}
    return out


def _groupby(items: List[Dict[str, Any]], key) -> Dict[str, List[Dict[str, Any]]]:
    d: Dict[str, List[Dict[str, Any]]] = {}
    for it in items:
        d.setdefault(key(it), []).append(it)
    return d


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Judge 人工校准基线")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_sample = sub.add_parser("sample", help="抽样生成人工标注模板")
    p_sample.add_argument("--input", type=Path, required=True, help="results JSON（含 results[]）")
    p_sample.add_argument("-n", type=int, default=30)
    p_sample.add_argument("--seed", type=int, default=DEFAULT_SEED)
    p_sample.add_argument("--out", type=Path, required=True)

    p_agree = sub.add_parser("agreement", help="计算 judge 与人工的一致性")
    p_agree.add_argument("--labels", type=Path, required=True, help="sample 产出并已标注的 jsonl")
    p_agree.add_argument("--out", type=Path, default=None, help="报告写盘路径（默认 stdout）")

    args = parser.parse_args(argv)

    if args.cmd == "sample":
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        rows = sample_for_labeling(payload.get("results") or [], args.n, args.seed)
        counts = Counter(r["judge_bucket"] for r in rows)
        with args.out.open("w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"sampled {len(rows)} → {args.out}  bucket分布={dict(counts)}")
        print("人工标注：把每行 human_correct 填为 true/false，再跑 agreement")
        return 0

    labeled = [
        json.loads(line)
        for line in args.labels.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    report = agreement_report(labeled)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        args.out.write_text(text + "\n", encoding="utf-8")
        print(f"wrote → {args.out}")
    else:
        print(text)
    if "error" not in report:
        print(
            f"agreement={report['agreement']:.1%} "
            f"95%CI=[{report['agreement_ci95'][0]:.1%}, {report['agreement_ci95'][1]:.1%}] "
            f"kappa={report['cohens_kappa']}",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
