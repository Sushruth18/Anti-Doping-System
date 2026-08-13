# Adaptive Anti-Doping Defense Engine — Backend

<!--
Local development setup:

1. Create a virtual environment (from the /backend directory):
     python -m venv venv

2. Activate it:
     Windows (PowerShell):  .\venv\Scripts\Activate.ps1
     Windows (cmd.exe):     venv\Scripts\activate.bat
     macOS / Linux:         source venv/bin/activate

3. Install dependencies:
     pip install -r requirements.txt

4. Run the development server:
     uvicorn app.main:app --reload

   The API will be available at http://127.0.0.1:8000
   Health check: http://127.0.0.1:8000/health
-->

FastAPI backend scaffold. Currently exposes only a `/health` endpoint;
routes will be added under `app/routes/` as features are built out.
