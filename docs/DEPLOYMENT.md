# Deployment

This repo is split into:

- `frontend/`: a static HTML/JS site (deploy to GitHub Pages).
- `backend/`: a FastAPI API (deploy to a free web-service host like Render).

## 1) Deploy the FastAPI backend (Render free web service)

Render has a free tier for web services, but free services can spin down when idle. See Render docs for details.

This repo includes a `render.yaml` Blueprint so you can enable Render Auto-Deploy/PR previews.

Option A (recommended): **Blueprint**

1. In Render, create a **Blueprint** from this repo (it will pick up `render.yaml`).
2. Deploy, then copy the public base URL (example: `https://your-service.onrender.com`).

Option B: **Manual Web Service**

Create a new **Web Service** on Render from this GitHub repo and set:

- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`

After it deploys, copy the public base URL (example: `https://your-service.onrender.com`).

## 2) Configure the frontend (GitHub Pages)

1. In your GitHub repo, go to **Settings -> Pages** and set **Source** to **GitHub Actions**.
2. Set the backend URL for the Pages deployment:
   - **Settings -> Secrets and variables -> Actions -> Variables**
   - Add a variable named `BACKEND_URL` with your backend base URL (no trailing slash).
3. Push to `main` (or run the workflow manually) and GitHub Pages will deploy the `frontend/` folder.

## 3) Optional: override backend URL per session

The UI also supports an `api` query parameter:

`https://<your-pages-site>/?api=https://your-service.onrender.com`
