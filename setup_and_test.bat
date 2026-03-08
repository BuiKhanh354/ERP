@echo off
cd /d e:\gitclone\ERP
call venv\Scripts\activate.bat

echo ============================================ > setup_output.txt 2>&1
echo [1] Running migrate... >> setup_output.txt 2>&1
python manage.py migrate --no-color >> setup_output.txt 2>&1

echo. >> setup_output.txt 2>&1
echo ============================================ >> setup_output.txt 2>&1
echo [2] Running setup_accounts... >> setup_output.txt 2>&1
python manage.py setup_accounts >> setup_output.txt 2>&1

echo. >> setup_output.txt 2>&1
echo ============================================ >> setup_output.txt 2>&1
echo [3] Checking system... >> setup_output.txt 2>&1
python manage.py check --no-color >> setup_output.txt 2>&1

echo. >> setup_output.txt 2>&1
echo [DONE] >> setup_output.txt 2>&1
