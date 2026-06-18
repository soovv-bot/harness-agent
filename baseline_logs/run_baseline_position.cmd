@echo off
setlocal

set POSITION=%1
if "%POSITION%"=="" exit /b 2

cd /d D:\research\search_data_systhesis

set OUTPUT=D:\research\search_data_systhesis\baseline_results\seed123_position%POSITION%_baseline.json
set TRAJDIR=D:\research\search_data_systhesis\baseline_logs\pos%POSITION%
set OUTLOG=D:\research\search_data_systhesis\baseline_logs\pos%POSITION%.out
set ERRLOG=D:\research\search_data_systhesis\baseline_logs\pos%POSITION%.err

"D:\anaconda3\envs\agent_safety\python.exe" "D:\research\search_data_systhesis\run_baseline.py" --seed 123 --sample-size 10 --positions %POSITION% --output "%OUTPUT%" --trajectory-dir "%TRAJDIR%" 1>"%OUTLOG%" 2>"%ERRLOG%"
