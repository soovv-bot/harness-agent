"""Judge 校准基线 tests (M3 ③) — 分层抽样确定性 & 一致性指标正确性。

Invariant being tested: 固定 seed 的抽样可复算（校准基线必须稳定），
agreement/kappa 数学含义正确，未标注样本被干净地跳过。
"""

import json

import pytest

from scripts.analysis.judge_calibration import (
    agreement_report,
    cohens_kappa,
    main as calib_main,
    sample_for_labeling,
)


def _mk_results(n_correct=20, n_incorrect=15, n_grader_err=5, n_ungraded=3):
    out = []
    for i in range(n_correct):
        out.append({"task_index": i, "is_correct": True, "question_preview": f"q{i}",
                    "extracted_answer": "a", "correct_answer": "b"})
    for i in range(n_incorrect):
        out.append({"task_index": 100 + i, "is_correct": False, "question_preview": f"w{i}",
                    "extracted_answer": "a", "correct_answer": "c"})
    for i in range(n_grader_err):
        out.append({"task_index": 200 + i, "is_correct": False,
                    "grader_error_type": "timeout", "question_preview": f"e{i}"})
    for i in range(n_ungraded):
        out.append({"task_index": 300 + i, "is_correct": None, "question_preview": f"u{i}"})
    return out


class TestSampling:
    def test_deterministic(self):
        res = _mk_results()
        assert sample_for_labeling(res, 25) == sample_for_labeling(res, 25)

    def test_seed_changes_sample(self):
        res = _mk_results()
        a = {r["task_index"] for r in sample_for_labeling(res, 25, seed=1)}
        b = {r["task_index"] for r in sample_for_labeling(res, 25, seed=2)}
        assert a != b

    def test_stratified_buckets_covered(self):
        rows = sample_for_labeling(_mk_results(), 12)
        buckets = {r["judge_bucket"] for r in rows}
        assert {"correct", "incorrect", "grader_error", "ungraded"} <= buckets

    def test_small_pool_no_crash(self):
        rows = sample_for_labeling(_mk_results(2, 1, 0, 0), 30)
        assert len(rows) == 3

    def test_rows_have_labeling_fields(self):
        row = sample_for_labeling(_mk_results(), 1)[0]
        for k in ("task_index", "question_preview", "correct_answer",
                  "extracted_answer", "judge_verdict", "judge_bucket",
                  "human_correct", "human_note"):
            assert k in row
        assert row["human_correct"] is None


class TestKappa:
    def test_perfect_agreement(self):
        assert cohens_kappa([True, False, True, False], [True, False, True, False]) == pytest.approx(1.0)

    def test_degenerate_all_same(self):
        assert cohens_kappa([True, True], [True, True]) is None

    def test_chance_gives_zero(self):
        # 判 50/50，人工也 50/50，但独立分布恰好落在偶然一致
        j = [True] * 25 + [False] * 25
        h = [True] * 25 + [False] * 25
        k = cohens_kappa(j, h)
        assert k == pytest.approx(1.0)

    def test_empty(self):
        assert cohens_kappa([], []) is None

    def test_total_disagreement_negative(self):
        j = [True, False]
        h = [False, True]
        assert cohens_kappa(j, h) < 0


class TestAgreementReport:
    def _labeled(self):
        return [
            {"task_index": 1, "judge_verdict": True, "human_correct": True, "judge_bucket": "correct"},
            {"task_index": 2, "judge_verdict": True, "human_correct": False, "judge_bucket": "correct",
             "extracted_answer": "x", "correct_answer": "y", "human_note": "judge too lenient"},
            {"task_index": 3, "judge_verdict": False, "human_correct": True, "judge_bucket": "incorrect",
             "extracted_answer": "x", "correct_answer": "x"},
            {"task_index": 4, "judge_verdict": False, "human_correct": False, "judge_bucket": "incorrect"},
            {"task_index": 5, "judge_verdict": None, "human_correct": True, "judge_bucket": "grader_error"},
            {"task_index": 6, "judge_verdict": False, "human_correct": None, "judge_bucket": "incorrect"},
        ]

    def test_counts_and_disagreements(self):
        rep = agreement_report(self._labeled())
        assert rep["n_labeled"] == 4
        assert rep["skipped_unlabeled"] == 2  # one judge None, one human None
        assert rep["confusion"] == {"tp": 1, "fp": 1, "fn": 1, "tn": 1}
        assert rep["agreement"] == pytest.approx(0.5)
        assert len(report_disagreements(rep)) == 2
        idxs = {d["task_index"] for d in report_disagreements(rep)}
        assert idxs == {2, 3}
        # fp 样本上的 note 被透传
        note2 = next(d for d in report_disagreements(rep) if d["task_index"] == 2)
        assert note2["human_note"] == "judge too lenient"

    def test_by_bucket(self):
        rep = agreement_report(self._labeled())
        assert rep["by_bucket"]["correct"] == {"n": 2, "agreement": pytest.approx(0.5)}
        assert rep["by_bucket"]["incorrect"] == {"n": 2, "agreement": pytest.approx(0.5)}

    def test_ci_present_and_bounded(self):
        rep = agreement_report(self._labeled())
        lo, hi = rep["agreement_ci95"]
        assert 0.0 <= lo <= rep["agreement"] <= hi <= 1.0

    def test_no_labels(self):
        rep = agreement_report([{"task_index": 1, "human_correct": None}])
        assert "error" in rep and rep["n_labeled"] == 0


def report_disagreements(rep):
    return rep["disagreements"]


class TestCli:
    def test_sample_then_agreement_roundtrip(self, tmp_path, capsys):
        src = tmp_path / "res.json"
        src.write_text(json.dumps({"results": _mk_results()}), encoding="utf-8")
        labels = tmp_path / "lab.jsonl"
        assert calib_main(["sample", "--input", str(src), "-n", "12",
                           "--out", str(labels), "--seed", "7"]) == 0
        out = capsys.readouterr().out
        assert "sampled 12" in out and "bucket分布" in out

        # 标注：把 human_correct 一律填为 true（制造可预测的不一致）
        lines = [json.loads(l) for l in labels.read_text(encoding="utf-8").splitlines() if l.strip()]
        assert len(lines) == 12
        for l in lines:
            l["human_correct"] = True if l["judge_verdict"] is not None else None
        labels.write_text("\n".join(json.dumps(l) for l in lines), encoding="utf-8")

        report_path = tmp_path / "rep.json"
        assert calib_main(["agreement", "--labels", str(labels),
                           "--out", str(report_path)]) == 0
        rep = json.loads(report_path.read_text(encoding="utf-8"))
        graded = [l for l in lines if l["judge_verdict"] is not None]
        expected = sum(1 for l in graded if l["judge_verdict"]) / len(graded)
        assert rep["n_labeled"] == len(graded)
        assert rep["agreement"] == pytest.approx(expected)

    def test_ascii_safe_output(self, tmp_path):
        # 中文 question 不炸编码
        src = tmp_path / "res.json"
        src.write_text(json.dumps({"results": [
            {"task_index": 0, "is_correct": True, "question_preview": "老舍的原名是什么？"}
        ]}, ensure_ascii=False), encoding="utf-8")
        lab = tmp_path / "x.jsonl"
        calib_main(["sample", "--input", str(src), "-n", "1", "--out", str(lab)])
        assert "老舍" in lab.read_text(encoding="utf-8")
