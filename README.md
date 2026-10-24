# Jarvis News (Voice-Interactive News Briefing)

A local, voice-interactive daily news briefing app. FastAPI serves a Stark-inspired HUD, Exa searches recent news, and a local Ollama model turns selected full article text into spoken deep dives.

## Project structure

```text
.
├── app.py
├── requirements.txt
├── .env.example
├── .gitignore
└── static/
    └── index.html
```

The app creates `data/profile.json` the first time a profile is changed. It stores the user's name and tracked topics locally.

## Run locally

1. Create and activate a virtual environment, then install dependencies:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. Set your Exa API key and start Ollama with the configured model:

   ```bash
   cp .env.example .env
   # Set EXA_API_KEY in your shell or load it from .env using your preferred tool.
   ollama pull llama3
   ollama serve
   ```

   The application reads environment variables directly and does not load `.env` files automatically. For example:

   ```bash
   export EXA_API_KEY="your_exa_api_key"
   export OLLAMA_MODEL="llama3"
   ```

3. Start the app in the same environment where `EXA_API_KEY` is set. Choose one option:

   **Local only (HTTP):**
   ```bash
   uvicorn app:app --reload
   ```

   **Local network with HTTPS (mobile microphone and app installation):**
   ```bash
   uvicorn app:app --reload --host 0.0.0.0 --port 8000 \
     --ssl-certfile "$HOME/jarvis-local-tls/cert.pem" \
     --ssl-keyfile "$HOME/jarvis-local-tls/key.pem"
   ```
   Replace the certificate paths if you saved the `.pem` files elsewhere. Keep `key.pem` private. On your phone, open `https://<mac-wi-fi-ip>:8000` after trusting the certificate on that device.

4. Open <http://127.0.0.1:8000> or <https://127.0.0.1:8000>. Voice recognition works in browsers that support the Web Speech API (typically Chrome or Edge); the manual controls work in other browsers. Phone browsers require HTTPS for microphone access and app installation, so a plain HTTP address using your Mac's LAN IP cannot show a permission prompt or install the app. For Android, open the app in Chrome at its trusted HTTPS address and use **Install app** at the top of the page, or choose **⋮ → Install app / Add to Home screen**. The app requires a trusted certificate; see the local HTTPS instructions below. Open <http://127.0.0.1:8000/interactive_architecture.html> or <https://127.0.0.1:8000/interactive_architecture.html> for the interactive architecture map and workflow walkthroughs.

### Local HTTPS for mobile

For trusted HTTPS on a local Wi-Fi network, install [mkcert](https://github.com/FiloSottile/mkcert), run `mkcert -install` on the Mac, and generate a certificate for the Mac's current Wi-Fi IP address. Install mkcert's root certificate on the phone and explicitly trust it, then run Uvicorn with `--ssl-certfile` and `--ssl-keyfile` pointing to the generated files. Keep the private key private; do not commit it or transfer it to the phone. Android and browser certificate settings differ by version. A certificate warning that the phone has not trusted will prevent the app from meeting secure-context requirements.

The dashboard is a small installable web app: its manifest and service worker cache only the app shell. API-backed features still need the Mac and its network services to be available.

## Exa Monitor webhook receiver

Run the Monitor receiver as a separate service so a public ngrok tunnel does not expose the unauthenticated Jarvis dashboard/API:

1. When creating an Exa Monitor, set its webhook URL to `https://<your-ngrok-domain>/webhooks/exa` and subscribe to `monitor.run.completed`. Save the returned `webhookSecret` immediately; Exa only returns it at creation.
2. In a dedicated terminal, set the secret in the environment and start the receiver:

   ```bash
   export EXA_MONITOR_WEBHOOK_SECRET="<webhookSecret returned by Exa>"
   .venv/bin/uvicorn exa_webhook:app --host 127.0.0.1 --port 8001
   ```

   Confirm the receiver is running with `curl http://127.0.0.1:8001/healthz`. Keep the secret private. Do not put it in the repository, the monitor query, or logs.
3. In another terminal, start ngrok:

   ```bash
   ngrok http 8001
   ```

   Use the HTTPS forwarding domain printed by ngrok when configuring the monitor. Keep both processes running. If a temporary ngrok URL changes, update the monitor's webhook URL.
4. Exa posts signed events to `POST /webhooks/exa`. The receiver verifies `Exa-Signature` against the original request bytes using HMAC-SHA256 and `EXA_MONITOR_WEBHOOK_SECRET`, limits payloads to 2 MiB, and stores verified events in `data/exa-monitor-events.sqlite3`. Event IDs are unique, so retries are acknowledged as duplicates without storing the same event twice. The receiver does not expose event contents through an HTTP read endpoint.

The receiver listens on localhost port 8001; do not change it to `0.0.0.0` when using ngrok. Only the receiver is tunneled. Exa Monitor is not a Zero Data Retention API, and the SQLite database contains the delivered event payloads; protect the Mac account and remove the database when the stored events are no longer needed.

### View Monitor results in Jarvis

Start the Jarvis dashboard on port 8000 as usual, in addition to the receiver. The dashboard reads completed events from the same `data/exa-monitor-events.sqlite3` database. After a completed Monitor webhook has been received, open the Jarvis page and use **Exa Monitor News → Refresh updates**; the section also refreshes automatically once a minute. This is separate from daily briefing results.

If you override the database location, set `EXA_MONITOR_EVENTS_DB` to the same path in both service terminals before starting the receiver and the dashboard. The dashboard API only reads the local SQLite file; it does not expose the webhook receiver or its database over ngrok. Keep Monitor event data protected and delete it when no longer needed.

## API

- `GET /api/profile` — read the active profile and topics.
- `GET /api/profiles` — list available profiles.
- `POST /api/profiles` — create and activate a profile with `{"name":"..."}`.
- `POST /api/profiles/activate` — switch profiles with `{"profile_id":"..."}`.
- `PUT /api/profile` — update the name with `{"name":"..."}`.
- `PUT /api/profile/settings` — save the active profile's `{"hours":24,"top_n":10,"voice":"Samantha"}` briefing preferences.
- `POST /api/topics/add` — add a topic with `{"topic":"..."}`.
- `POST /api/topics/remove` — remove a topic with `{"topic":"..."}`.
- `GET /api/status` — check the app, Exa, Ollama/model, browser speech recognition, and local audio status.
- `GET /api/monitors/news` — read recent completed Exa Monitor results stored by the local webhook receiver.
- `GET /api/speech/voices` — list voices installed on the macOS host running FastAPI.
- `POST /api/speech` — synthesize `{"text":"...","voice":"..."}` into a WAV audio response for browser playback.
- `POST /api/news` — search tracked topics with `{"hours":24,"top_n":10}`. Either field may be omitted to use the active profile's saved preference. The look-back value can be 1–168 hours (up to seven days); top N can be 3–20 stories across all topics. The backend selects stories in relevance-ordered rounds, taking at most one distinct story per topic per round to distribute coverage. Topics with fewer eligible stories or duplicates leave slots for other topics in later rounds. If the number of topics with news exceeds Top N, not every topic can fit; the response reports covered and uncovered topics. Similar headlines and identical URLs are deduplicated as likely reports of the same event.
- `POST /api/news/deep-dive` — retrieve and synthesize full text for selected articles with `{"urls":["https://..."]}`.

Choose **Web interactive mode** to fetch a briefing and use on-screen controls; after results load, choose **Read headlines** whenever you want to hear them. Choose **Voice mode** to speak commands and hear the briefing. Voice commands include “add topic quantum computing”, “remove topic Indian politics”, “stop tracking Indian politics”, and “run morning briefing”; topic commands are recognized even while the assistant is waiting for story numbers or topic follow-up. Pause/resume and blocked-playback controls stay in the briefing panel. Use **Reset** in Signal intelligence to clear the current articles and briefing workflow before starting fresh. The HUD animates and changes color to distinguish web interaction, voice listening, and speech playback. For article selection, use story checkboxes or type comma-separated numbers. Topics are managed as removable chips in a single wrapping editor: type a topic and press Enter or select Add topic. On macOS, speech is rendered by the host's native `say` voices and delivered as WAV audio to the browser. Filter installed voices by language and locale, then test the selected voice. The system status includes topic setup and a speaker test that asks you to confirm whether you heard the sample. The server requires macOS `say` and `afconvert` for local audio. Headlines and summaries stay compact, with full Exa highlights/article text available from each story's expandable details. The greeting, date, weekday, and clock use the browser's local time. Exa searches are restricted to results published within the selected hours before the request and use token-efficient highlights. Full article text is fetched from Exa only for stories selected for a deep dive. Profiles are stored in the local profile JSON file and maintain independent names, topics, look-back periods, story counts, and speech voices; new profiles start without topics and use default settings.
