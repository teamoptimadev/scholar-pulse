Here’s a minimal **from-scratch** setup (about 15 lines):

```bash
# Prerequisites: Docker, uv, Bun

cp .env.example .env
docker compose up -d

cd backend && cp .env.example .env && uv sync
uv run alembic upgrade head
uv run python scripts/seed.py --scale 100
uv run uvicorn app.main:app --reload --port 8000

cd ../client && bun install && bun run dev
```

**URLs**
- App: http://localhost:3000  
- API: http://localhost:8000/docs  

**Login (after seed)**
- Admin: `admin@demo.com` / `admin123`  
- Faculty: `faculty@demo.com` / `faculty123`  
- Student: `20231CSE0260` / `student123`  

**Notes**
### Installing uv

macOS / Linux:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

macOS with Homebrew:
```bash
brew install uv
```

Windows PowerShell:
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Restart your terminal or reload its shell configuration, then verify with `uv --version`. See the [official installation documentation](https://docs.astral.sh/uv/getting-started/installation/).

If you want this added to the README as a short block, switch to **Agent mode** and I can update it.