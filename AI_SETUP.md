# AI Setup

Use this after pulling the repo so the AI features work on a new machine.

## 1. Create environment config

Copy `.env.example` to `.env` and adjust values if needed.

Important AI values:

- `OLLAMA_URL=http://localhost:11434/api/chat`
- `OLLAMA_MODEL=qwen3:4b`

## 2. Install Python dependencies

```powershell
cd E:\gitclone\ERP
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 3. Train the HR attrition model

```powershell
python .\ai\train_attrition.py
```

This creates:

- `ai/models/attrition_model.pkl`

If the HR CSV is missing, the script will download it automatically from the IBM dataset repo and save it into `ai/data`.

## 4. Install Ollama

Install Ollama on Windows, then pull the model:

```powershell
ollama pull qwen3:4b
```

If you want a lighter or different model, change `OLLAMA_MODEL` in `.env` and pull that model instead.

## 5. Run the project

```powershell
python manage.py runserver
```

## 6. Test AI endpoints

- `POST /api/ai/chat`
- `POST /api/ai/predict-attrition`
- `GET /api/ai/forecast`
- `GET /api/ai/detect-anomaly`
- `POST /api/ai/recommend-resource`
- `GET /api/ai/risk-detect`
- `GET /api/ai/report`

## 7. One-command helper

You can also run:

```powershell
.\scripts\setup_ai.ps1
```

This installs dependencies, trains the attrition model, and pulls the Ollama model if the CLI is already installed.
