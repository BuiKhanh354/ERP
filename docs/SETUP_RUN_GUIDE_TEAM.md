# Huong Dan Cai Dat Va Chay Du An (Cho Team)

## 1) Yeu cau moi truong
- Windows 10/11
- Python 3.12.x
- SQL Server (MSSQLSERVER) dang `Running`
- Git
- (Tuy chon AI) Ollama neu muon chay cac chuc nang AI dung LLM

## 2) Clone du an
```powershell
git clone <repo-url> E:\gitclone\ERP
cd E:\gitclone\ERP
```

## 3) Tao virtual env va cai thu vien
```powershell
py -3.12 -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

## 4) Cau hinh DB SQL Server
- Mo file cau hinh DB cua Django (thuong trong `ERP/settings.py`).
- Dien dung:
  - `HOST`
  - `PORT`
  - `NAME`
  - `USER`
  - `PASSWORD`
- Neu dung SQL Server Authentication thi bat buoc dung user/pass.

## 5) Migrate DB
```powershell
.\venv\Scripts\python.exe manage.py migrate
```

## 6) Seed role/quyen (neu DB moi)
```powershell
.\venv\Scripts\python.exe manage.py seed_rbac_v2
```

## 7) Chay server
```powershell
.\venv\Scripts\python.exe manage.py runserver
```
- Truy cap: `http://127.0.0.1:8000`

## 8) (Tuy chon) Chay AI LLM qua Ollama
```powershell
ollama serve
ollama run qwen3:4b
```
- Neu khong co Ollama, mot so chuc nang AI se fallback.

## 9) Test nhanh sau khi chay
```powershell
.\venv\Scripts\python.exe manage.py check
```
- Ky vong: `System check identified no issues`.

## 10) Loi thuong gap
- `Invalid object name ...`:
  - Thieu bang do chua migrate du hoac DB dang tro nham.
- `Login timeout expired` / `08001`:
  - Sai host/user/pass SQL Server hoac dich vu SQL chua chay.
- AI tra loi 500:
  - Kiem tra Ollama dang chay chua.
  - Kiem tra DB ket noi OK chua.

## 11) Goi y quy trinh cho team
1. Pull code moi nhat
2. Activate venv
3. `pip install -r requirements.txt` (neu co cap nhat)
4. `python manage.py migrate`
5. `python manage.py runserver`
