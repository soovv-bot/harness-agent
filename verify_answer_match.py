"""
验证脚本：检查每个有答案的轨迹是否都有 answer_match 字段
"""

import json
from pathlib import Path
from tqdm import tqdm


def main():
    trajectory_dir = Path("data/trajectories/deepseek-chat")
    task_files = list(trajectory_dir.glob("task_*.json"))

    print(f"Total task files: {len(task_files)}")

    # 统计
    has_answer_with_match = 0      # 有答案且有 answer_match
    has_answer_no_match = 0        # 有答案但没有 answer_match
    no_answer = 0                  # 没有答案
    missing_match_files = []       # 缺少 answer_match 的文件列表

    for task_file in tqdm(task_files, desc="Checking"):
        with open(task_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        task_index = data.get("task_index")
        answer = data.get("answer")
        answer_match = data.get("answer_match")

        if answer:
            if answer_match is not None:
                has_answer_with_match += 1
            else:
                has_answer_no_match += 1
                missing_match_files.append({
                    "task_index": task_index,
                    "file": task_file.name,
                    "answer_preview": answer[:100] + "..." if len(answer) > 100 else answer
                })
        else:
            no_answer += 1

    print("\n" + "=" * 60)
    print("VERIFICATION RESULTS")
    print("=" * 60)
    print(f"Total files checked: {len(task_files)}")
    print(f"Has answer + has answer_match: {has_answer_with_match}")
    print(f"Has answer + NO answer_match: {has_answer_no_match}")
    print(f"No answer: {no_answer}")
    print("=" * 60)

    if missing_match_files:
        print(f"\nFiles missing answer_match ({len(missing_match_files)}):")
        for item in missing_match_files[:10]:  # 只显示前10个
            print(f"  Task {item['task_index']}: {item['file']}")
            print(f"    Answer: {item['answer_preview']}")
        if len(missing_match_files) > 10:
            print(f"  ... and {len(missing_match_files) - 10} more")
    else:
        print("\n✓ All tasks with answers have answer_match field!")


if __name__ == "__main__":
    main()
