"""
整理现有轨迹文件到新的目录结构

将 data/trajectories/deepseek-chat/ 下的轨迹文件按照答案状态分类到子目录：
- no_answer/: 没有答案的
- answer_wrong/: 有答案但不对的
- answer_correct/: 有答案且正确的
"""

import json
import shutil
from pathlib import Path
from tqdm import tqdm


def organize_trajectories(trajectory_dir: Path):
    """整理轨迹文件到子目录"""

    # 创建子目录
    subdirs = {
        "no_answer": trajectory_dir / "no_answer",
        "answer_wrong": trajectory_dir / "answer_wrong",
        "answer_correct": trajectory_dir / "answer_correct",
    }

    for subdir in subdirs.values():
        subdir.mkdir(parents=True, exist_ok=True)

    # 统计
    stats = {
        "no_answer": 0,
        "answer_wrong": 0,
        "answer_correct": 0,
        "skipped": 0,
    }

    # 获取所有任务文件（排除子目录中的）
    task_files = [f for f in trajectory_dir.glob("task_*.json") if f.parent == trajectory_dir]
    print(f"Found {len(task_files)} task files to organize")

    for task_file in tqdm(task_files, desc="Organizing"):
        with open(task_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        answer = data.get("answer")
        answer_match = data.get("answer_match")

        # 确定目标目录
        if not answer:
            target_dir = "no_answer"
        elif answer_match:
            target_dir = "answer_correct"
        else:
            target_dir = "answer_wrong"

        # 移动文件
        target_path = subdirs[target_dir] / task_file.name

        if target_path.exists():
            stats["skipped"] += 1
            print(f"Skipped (already exists): {task_file.name}")
            continue

        shutil.move(str(task_file), str(target_path))
        stats[target_dir] += 1

    print("\n" + "=" * 60)
    print("ORGANIZATION SUMMARY")
    print("=" * 60)
    print(f"Total processed: {len(task_files)}")
    print(f"No answer: {stats['no_answer']}")
    print(f"Answer wrong: {stats['answer_wrong']}")
    print(f"Answer correct: {stats['answer_correct']}")
    print(f"Skipped (already in subdirs): {stats['skipped']}")
    print("=" * 60)


def main():
    trajectory_dir = Path("data/trajectories/deepseek-chat")

    if not trajectory_dir.exists():
        print(f"Trajectory directory not found: {trajectory_dir}")
        return

    organize_trajectories(trajectory_dir)


if __name__ == "__main__":
    main()
