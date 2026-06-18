@echo off
cd /d D:\research\search_data_systhesis
"D:\anaconda3\envs\agent_safety\python.exe" "D:\research\search_data_systhesis\run_baseline.py" --seed 123 --sample-size 10 --positions 1 --output "D:\research\search_data_systhesis\baseline_results\seed123_position1_baseline.json" --trajectory-dir "D:\research\search_data_systhesis\baseline_logs\pos1" 1>"D:\research\search_data_systhesis\baseline_logs\pos1.out" 2>"D:\research\search_data_systhesis\baseline_logs\pos1.err"
