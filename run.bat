@echo off
set PYTHONUNBUFFERED=1
call venv\Scripts\activate.bat
python manage.py makemigrations > run_log.txt 2>&1
python manage.py migrate >> run_log.txt 2>&1
python runserver.py >> run_log.txt 2>&1
