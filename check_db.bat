@echo off
set PYTHONUNBUFFERED=1
call venv\Scripts\activate.bat
python manage.py makemigrations > make_out4.txt 2>&1
