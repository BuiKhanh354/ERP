@echo off
echo ========================================
echo  Running ERP Database Upgrade
echo ========================================

cd /d e:\gitclone\ERP

echo.
echo [1/3] Activating venv...
call venv\Scripts\activate.bat

echo.
echo [2/3] Running SQL Upgrade Script...
python run_upgrade_sql.py
if %errorlevel% neq 0 (
    echo ERROR: SQL upgrade failed!
    pause
    exit /b 1
)

echo.
echo [3/3] Running Django migrations...
python manage.py makemigrations core projects budgeting
python manage.py migrate --run-syncdb

echo.
echo ========================================
echo  Upgrade Complete!
echo ========================================
echo.
echo Verifying Django system check...
python manage.py check

pause
