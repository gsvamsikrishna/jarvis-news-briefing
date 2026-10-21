# Jarvis Personal Intelligence

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

3. Start the app in the same environment where `EXA_API_KEY` is set:

   ```bash
   uvicorn app:app --reload
   ```

4. Open <http://127.0.0.1:8000>. Voice recognition works in browsers that support the Web Speech API (typically Chrome or Edge); the manual controls work in other browsers. Open <http://127.0.0.1:8000/architecture> for the interactive architecture map and workflow walkthroughs.

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
- `GET /api/speech/voices` — list voices installed on the macOS host running FastAPI.
- `POST /api/speech` — synthesize `{"text":"...","voice":"..."}` into a WAV audio response for browser playback.
- `POST /api/news` — search tracked topics with `{"hours":24,"top_n":10}`. Either field may be omitted to use the active profile's saved preference. The look-back value can be 1–168 hours (up to seven days); top N can be 3–20 stories across all topics. The backend first reserves one distinct story per topic with available news, then fills remaining slots by Exa relevance. If the number of topics with news exceeds Top N, not every topic can fit; the response reports covered and uncovered topics. Similar headlines and identical URLs are deduplicated as likely reports of the same event.
- `POST /api/news/deep-dive` — retrieve and synthesize full text for selected articles with `{"urls":["https://..."]}`.

Choose **Web interactive mode** to fetch a briefing and use on-screen controls; after results load, choose **Read headlines** whenever you want to hear them. Choose **Voice mode** to speak commands and hear the briefing. Voice commands include “add topic quantum computing”, “remove topic Indian politics”, “stop tracking Indian politics”, and “run morning briefing”; topic commands are recognized even while the assistant is waiting for story numbers or topic follow-up. Pause/resume and blocked-playback controls stay in the briefing panel. Use **Reset** in Signal intelligence to clear the current articles and briefing workflow before starting fresh. The HUD animates and changes color to distinguish web interaction, voice listening, and speech playback. For article selection, say each story number separately (for example, “one, two, three”) or type comma-separated numbers. Topics are managed as removable chips in a single wrapping editor: type a topic and press Enter or select Add topic. On macOS, speech is rendered by the host's native `say` voices and delivered as WAV audio to the browser. Filter installed voices by language and locale, then test the selected voice. The system status includes topic setup and a speaker test that asks you to confirm whether you heard the sample. The server requires macOS `say` and `afconvert` for local audio. Headlines and summaries stay compact, with full Exa highlights/article text available from each story's expandable details. The greeting, date, weekday, and clock use the browser's local time. Exa searches are restricted to results published within the selected hours before the request and use token-efficient highlights. Full article text is fetched from Exa only for stories selected for a deep dive. Profiles are stored in the local profile JSON file and maintain independent names, topics, look-back periods, story counts, and speech voices; new profiles start without topics and use default settings.
