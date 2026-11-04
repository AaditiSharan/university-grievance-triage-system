# Deployment Guide — UniResolve AI (University Grievance Triage System)

This guide walks you through deploying UniResolve AI.

---

## Architecture Overview

UniResolve AI consists of two components:
- **Backend**: Python 3.10+ FastAPI API (`src.api.main:app`), SQLite or PostgreSQL with SQLAlchemy, and Scikit-Learn ML models.
- **Frontend**: Vite + React + TypeScript + TailwindCSS SPA (`frontend/`).

You can deploy the system using either:
1. **Option 1 (Recommended — Single Container)**: Render, Railway, Fly.io, or VPS using the included `Dockerfile`. FastAPI automatically serves the built React frontend and the API under one domain with **no CORS configuration** required.
2. **Option 2 (Decoupled PaaS)**: Backend on **Render** (Web Service) + Frontend on **Vercel** / **Netlify** (Static Site).
3. **Option 3 (Self-Hosted Docker Compose)**: Run directly on any Linux VPS or server with `docker compose up -d`.

---

## Environment Variables Reference

| Variable | Required | Default | Description |
| :--- | :--- | :--- | :--- |
| `SECRET_KEY` | **Yes (Production)** | Auto-generated random string | Secret key for signing JWT tokens. Generate with `python -c "import secrets; print(secrets.token_urlsafe(32))"`. |
| `FRONTEND_ORIGINS` | No | `http://localhost:5173,http://localhost:3000` | Comma-separated list of allowed CORS origins (e.g., `https://your-frontend.vercel.app`), or `*` to allow all. |
| `STAFF_EMAIL_DOMAINS` | No | `example.edu,university.edu` | Comma-separated domain names permitted for staff/faculty self-registration. |
| `DATABASE_URL` | No | `sqlite:///./grievances.db` | SQLAlchemy connection string. Supports SQLite or PostgreSQL (e.g. `postgresql://user:pass@host/dbname`). |
| `PORT` | No | `8000` | Port for the Uvicorn server (automatically provided by Render/Railway/Fly.io/Cloud Run). |
| `VITE_API_URL` | No (Frontend only) | `/api` | Set to your backend API URL (e.g., `https://your-api.onrender.com/api`) when deploying the frontend separately. |

---

## Option 1: Deploy on Render via Docker (Fastest & Free)

Deploy both the backend and frontend together as a single Render Web Service.

### Steps:
1. Push your updated code to your GitHub repository.
2. Go to [Render Dashboard](https://dashboard.render.com/) and click **New +** > **Web Service**.
3. Connect your GitHub repository: `university-grievance-triage-system`.
4. Configure service settings:
   - **Language / Runtime**: `Docker`
   - **Dockerfile Path**: `Dockerfile` (root directory)
   - **Plan**: `Free`
5. Under **Environment Variables**, add:
   - `SECRET_KEY`: click **Generate** or paste a random 32-character string.
   - `STAFF_EMAIL_DOMAINS`: your institution domains (e.g. `youruniversity.edu`).
   - `FRONTEND_ORIGINS`: `*`
6. Click **Create Web Service**.
7. Render will build the React frontend and Python backend, run health checks at `/api/health`, and publish your app at `https://<service-name>.onrender.com`.

---

## Option 2: Decoupled Deployment (Render + Vercel)

If you prefer hosting the React frontend on Vercel's global CDN and the FastAPI backend on Render.

### Part A: Deploy the Backend on Render
1. In Render, select **New +** > **Web Service** > connect your GitHub repo.
2. Select **Python 3** environment:
   - **Build Command**: `pip install -r requirements-prod.txt`
   - **Start Command**: `python -m uvicorn src.api.main:app --host 0.0.0.0 --port $PORT`
3. Add Environment Variables:
   - `SECRET_KEY`: `<secure-random-key>`
   - `FRONTEND_ORIGINS`: `https://<your-vercel-app>.vercel.app`
   - `STAFF_EMAIL_DOMAINS`: `youruniversity.edu`
4. Copy the backend URL once deployed (e.g. `https://uniresolve-api.onrender.com`).

### Part B: Deploy the Frontend on Vercel
1. Go to [Vercel](https://vercel.com/) and click **Add New** > **Project**.
2. Select your repository `university-grievance-triage-system`.
3. In project settings:
   - **Root Directory**: `frontend`
   - **Framework Preset**: `Vite`
   - **Build Command**: `npm run build`
   - **Output Directory**: `dist`
4. In **Environment Variables**, add:
   - `VITE_API_URL`: `https://uniresolve-api.onrender.com/api` (replace with your Render backend URL)
5. Click **Deploy**. Vercel will use the included `frontend/vercel.json` rewrite configuration for seamless client-side routing.

---

## Option 3: Deploy with Docker Compose (VPS / Self-Hosted)

For DigitalOcean, AWS EC2, Linode, or any Linux server:

1. Clone your repo onto the server:
   ```bash
   git clone https://github.com/AaditiSharan/university-grievance-triage-system.git
   cd university-grievance-triage-system
   ```

2. Start the service:
   ```bash
   docker compose up -d --build
   ```

3. The application is live at `http://<server-ip>:8000`. Database data persists in the `grievance_data` volume.

---

## Initial Admin Account Setup in Production

To create an administrator account in production:
1. Register a user in the web UI (e.g. username `admin_user`).
2. Run this one-liner in your server terminal or Render Shell:
   ```bash
   python -c "from src.db.connection import SessionLocal; from src.db.models import User; db=SessionLocal(); user=db.query(User).filter_by(username='admin_user').one(); user.role='admin'; db.commit(); db.close(); print('Admin role granted')"
   ```
3. Refresh the web UI; the user now has full administrative privileges.
