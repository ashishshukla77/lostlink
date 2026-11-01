# LOSTLINK

LOSTLINK is a Streamlit campus lost-and-found demo. It pairs public lost/found report details, ranks likely matches with transparent Python scoring, and can ask Sarvam to explain the strongest candidates.

## Run locally

Python 3.10 or newer is recommended. From the project folder in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
streamlit run app.py
```

The sample reports and deterministic matcher work without an API key. To enable Sarvam explanations, either set `SARVAM_API_KEY` in the process environment or add it to the ignored `.env` file. The app uses Sarvam Chat Completions with `sarvam-105b` and validates the structured JSON response. See [Sarvam Chat Completions](https://docs.sarvam.ai/api/token-factory/chat-completions).

## Deploy on Streamlit Community Cloud

1. Push this project folder to a GitHub repository. Keep `.env` and `.streamlit/secrets.toml` out of Git; `.gitignore` excludes both.
2. In Streamlit Community Cloud, create an app from that repository and set the app file to `app.py`. It installs dependencies from `requirements.txt`.
3. In the app's **Settings → Secrets**, add:

   ```toml
   SARVAM_API_KEY = "your Sarvam API key"
   ```

4. Deploy. The app reads this value from Streamlit secrets. If no key is configured or Sarvam is unavailable, local matching remains available.

## Features

- Lost and found forms, optional photos, and session-only reports.
- Dashboard counts, recent reports, and quick report buttons.
- Four sample lost/found pairs for immediate evaluation.
- Hybrid ranking by description, category, colour, location, and time; contradictions cap the score.
- Optional Sarvam explanations for up to five leading pairs in one request.
- Safe verification suggestions and a simulated contact request that sends no message.

Private identifying details stay in the session and are not sent to Sarvam or displayed on public match cards. This demo has no authentication or persistent storage. A match is a lead, not proof of ownership or a claim that an item was recovered.
