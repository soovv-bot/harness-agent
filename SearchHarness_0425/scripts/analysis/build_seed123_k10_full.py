import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = ROOT.parent
OUTPUT_PATH = ROOT / "data" / "seed123_k10_full.json"


def _load_question_from_baseline(pos: int) -> tuple[str, str]:
    path = PROJECT_ROOT / "baseline_results" / f"seed123_position{pos}_baseline.json"
    if not path.exists():
        return "", ""
    data = json.loads(path.read_text(encoding="utf-8"))
    result = (data.get("results") or [{}])[0]
    answer = result.get("correct_answer", "")
    task = (result.get("agent_metadata") or {}).get("task", "")
    match = re.search(r"Question:\n(.*)", task, re.S)
    question = match.group(1).strip() if match else ""
    return question, answer


def _load_question_from_trajectories(pos: int) -> str:
    for path in sorted((ROOT / "logs").glob(f"**/task_{pos:06d}.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        question = (data.get("metadata") or {}).get("question", "")
        if question:
            return question
    return ""


def main() -> None:
    manifest_path = ROOT / "data" / "seed123_k10_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    by_pos = {int(item["sample_position"]): item for item in manifest}
    full = []
    for pos in range(10):
        question, answer = _load_question_from_baseline(pos)
        if not question:
            question = _load_question_from_trajectories(pos)
        if not answer:
            answer = by_pos[pos].get("answer", "")
        if not question or not answer:
            raise RuntimeError(f"Missing local question/answer for position {pos}")
        full.append({
            "sample_position": pos,
            "question": question,
            "answer": answer,
        })
    OUTPUT_PATH.write_text(json.dumps(full, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
