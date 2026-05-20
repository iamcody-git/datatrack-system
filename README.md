# Data Track — Streamlit App

Trading journal and analytics dashboard (web). Deploy on [Render](https://render.com) or run locally.

## Project files (deploy)

```
data-track-/
├── streamlit_app.py      # Web UI
├── app_core.py           # Database, calculator, analytics
├── requirements.txt      # Python dependencies
├── render.yaml           # Render deploy config
├── .streamlit/config.toml
└── .gitignore
```

Runtime (created automatically): `data_track.db`, `uploads/`

## Run locally

```powershell
cd data-track-
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run streamlit_app.py
```

Open **http://localhost:8501**

## Deploy on Render

1. Push this folder to GitHub.
2. Render → **New** → **Blueprint** → connect the repo.
3. Deploy (uses `render.yaml`).
4. Optional: add `APP_PASSWORD` in **Environment** to require login.

**Free tier:** data may reset when the service redeploys. Back up via sidebar **Download database**.

**Paid tier:** uncomment `disk` and `DATA_DIR=/data` in `render.yaml` for persistent storage.

## Features

- Live FX + NEPSE ticker
- Position calculator → active trade → close with P&L
- Trade log, analytics, equity charts
- Daily & weekly journal (save, toast, delete)
- Excel export

## Optional local password

Create `.streamlit/secrets.toml`:

```toml
APP_PASSWORD = "your-password"
```

Or set environment variable `APP_PASSWORD`.
