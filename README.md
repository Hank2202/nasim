# The Summit of Realms - Live Geopolitical Strategy Simulation Platform

A lightweight, real-time web application built for live educational simulations. It runs locally on a facilitator's laptop (`0.0.0.0:5000`) and serves real-time responsive interfaces to students' smartphones and room projectors over a local Wi-Fi network with **zero external internet required**.

---

## 🌟 Key Features

- **Self-Contained (works offline or hosted)**: Zero reliance on external CDNs or web fonts. Light parchment-and-gold fantasy theme with storybook serif headings (system fonts), embedded SVG emblems, and synthesized Web Audio bells.
- **Dedicated Projector Screen (`/projector`)**: parchment map of the Continent (nations not playing shown as unclaimed lands) with a Council of Nations panel. Designed for classroom/auditorium projectors. Features:
  - Big Turn indicator and giant countdown timer.
  - Continental Delegations Board showing public standing, vitality, stability, votes, and conditions (never reveals secret agendas!).
  - Live breaking news ticker and room Wi-Fi QR code.
  - Dynamic Plenary Floor mode: when a Flash Assembly is active, it transforms into a full-screen roll-call visualizer with real-time weighted voting bars.
- **Comprehensive Game Overview & Guide (`/overview`)**:
  - Detailed simulation primer explaining the 6 sovereign nations, starting endowments, and geography.
  - Socioeconomic formulas and mathematical laws cheat sheet (starvation thresholds, technological efficiency, plutocratic drift, complacency paradox).
  - Parliamentary statutory resolution dockets, domestic governance levers, the Spireopedia quiz, and room setup guide.
- **Mobile Participant Cockpit (`/realm/<id>`)**:
  - **Persistent Bottom Navigation Bar**: Six tabs: **Realm** (stats, decrees, secret directives), **World** (news + continental registry), **Trade**, **Motions**, **Wiki** (Spireopedia, reading only) and **Quiz** (questions, answering only).
  - Secret Uncomfortable Domestic Directive (classified expandable drawer).
  - Live resource telemetry (Grain, Cores, Silk) and state metrics bars (Vitality, Standing, Stability).
  - Real-time P2P Trading Hub with atomic transfers and pending trade notification badges.
  - Player-driven emergency motions with a **Second Motion** trigger.
  - 60-Second Flash Assembly Modal Overlay with animated countdown and live roll-call.
- **Random events**:
  - During each working session the game posts small news items (default 6 per turn, 50 different ones, good and bad) that hit one nation. Each resource an item touches moves by a random amount between 0 and the largest change set on the setup screen (default 5; decimals allowed), at least 1. The share of good news depends on difficulty.
  - **Large disasters** (12: earthquake, tsunami, drought, blight, reactor breach, plague, revolt, border surge, dragon raid, great storm, tornado swarm, meteor shower; usually −10 to −25) strike at random only when *Large disasters per turn* is above 0 — the Armageddon scenario sets 3. They show on the projector map.
  - The famine storyline's crises (Round 2 border incident, Round 3 Great Famine) are built in. Catalog crises can also be triggered by hand (**⚡ Trigger Next Recommended Crisis**, the catalog dropdown), and there are **Good news now**, **Bad news now** and **Random disaster now** buttons.
- **Facilitator Command Deck (`/admin`)**:
  - Local LAN IP gateway & projected SVG QR code.
  - One-click launcher for the `/projector` display.
  - Turn & timer controls with Web Audio chime broadcasts.
  - Clean real-time telemetry grid with inline `+` / `-` override controls (no raw IDs!).
  - Flash Assembly manager with override controls (Force Pass, Force Fail, Extend +30s, Dismiss).
- **Hidden Socioeconomic Engine**:
  - **Per-Turn Consumption**: -20 baseline Alchemical Grain per operational turn.
  - **The Starvation Threshold**: If Grain drops to $\le 0$, automatic penalty of -25 Public Vitality and -20 Civil Stability.
  - **The Complacency Paradox**: If Civil Stability $\ge 85$ and Public Vitality $\ge 85$, domestic output slumps by 10% each turn unless luxury Echo Silk is expended.
  - **Technological Efficiency**: If Aether Cores $\ge 75$, permanently cuts grain consumption by 25% (-15 instead of -20).
  - **Plutocratic Drift**: The realm with highest total tangible wealth gains +1 bonus Assembly Vote, but suffers -5 Civil Stability per turn due to domestic inequality.
  - **Dynamic Voting Weights**: Derived from Diplomatic Standing ($\ge 80 \to 3$ votes, $45\text{--}79 \to 2$ votes, $< 45 \to 1$ vote) plus Plutocratic Drift.
- **State Persistence**: Uses SQLite (`summit.db`) so server restarts or laptop battery sleeps never wipe simulation progress.

---

## 📜 Quick Game Rundown & Rules at a Glance

### 1. Setting & Objective
Set three centuries after the **Great Convergence**, six sovereign nations convene at the **Neutral Spire** for a decisive **3-Turn Diplomatic Summit**. Continental harvest shortfalls and technological disparity threaten war and collapse. Every delegation must balance:
1. **Domestic Survival**: Preventing famine by keeping alchemical grain silos supplied.
2. **Continental Governance**: Passing or vetoing statutory resolutions during Plenary Assembly.
3. **Classified Directives**: Achieving their secret win-condition by the end of Turn 3.

---

### 2. The 6 Sovereign Delegations
| Delegation | Seats | Grain | Cores | Silk | Military | Vitality | Standing | Stability | Votes | Public mandate |
| :--- | :-: | :-: | :-: | :-: | :-: | :-: | :-: | :-: | :-: | :--- |
| 🌿 **Sylvan Concordat** | 2 | 100 | 25 | 30 | 25 | 85 | 65 | 80 | 2 | No country starving at the end |
| ⚒️ **Iron Val-Khor** | 3 | 30 | 80 | 25 | 65 | 70 | 50 | 70 | 2 | 4 of 6 countries reach 60 Cores |
| ☀️ **Solaris Ascendancy** | 4 | 50 | 40 | 75 | 45 | 85 | 90 | 80 | 3 | 3 resolutions pass with 4+ countries in favour |
| 🌙 **Umbral Enclave** | 1 | 40 | 70 | 30 | 55 | 65 | 40 | 70 | 1 | No country above 90 Military |
| ⚓ **Aquila Maritime League** | 2 | 50 | 40 | 80 | 35 | 80 | 70 | 70 | 2 | Every country trades with 2+ partners |
| 🛡️ **Aethelgard Dominion** | 3 | 60 | 50 | 25 | 80 | 80 | 55 | 85 | 2 | No country ends below 50 Stability |

Values follow the facilitator notes (`MGV 2026 školení s Johanem.md`) and live in `scenario_config.json`. Secret missions are in the config's `secret_missions_pool`.

---

### 3. Core Engine Formulas & Socioeconomic Laws
- **Dynamic Assembly Votes**:
  - Diplomatic Standing $\ge 80 \implies$ **3 Votes**
  - Diplomatic Standing $45\text{--}79 \implies$ **2 Votes**
  - Diplomatic Standing $< 45 \implies$ **1 Vote**
  - Reigning Continental Plutocrat (highest total Grain + Cores + Silk) $\implies$ **+1 Bonus Vote**
- **Grain Consumption & Starvation**:
  - Baseline: **-20 Grain** consumed every operational turn.
  - With **Technological Efficiency** (Cores $\ge 75$): Grain consumption drops permanently by 25% to **-15 Grain**.
  - **Starvation Penalty**: If Grain drops to $\le 0 \implies$ immediate penalty of **-25 Vitality** and **-20 Stability**.
- **Plutocratic Drift**: The wealthiest realm gains +1 Assembly Vote, but suffers **-5 Stability per turn** due to domestic inequality.
- **Complacency Paradox**: If both Vitality $\ge 85$ and Stability $\ge 85 \implies$ **-10% domestic output slump** unless luxury Echo Silk is expended (via Grand Gala).

---

### 4. Turn Cadence & Workshop Flow (3 Turns Total)
1. **Working & Bilateral Trade Session (default 20:00, set on the setup screen)**:
   - Roam the room freely for face-to-face bilateral diplomacy.
   - Execute instant atomic P2P trades (Grain, Cores, Silk, Military Power).
   - Enact internal state decrees (relief, forges, galas, security, mustering).
   - Read the Spireopedia and answer the shared quiz (+5 of a resource per correct answer; −5 of the same resource and a permanent lock per wrong answer).
   - Author statutory resolutions for the Plenary docket.
2. **Plenary Floor Debate & Assembly vote (default 3:00 vote in Turns 1–2; 5:00 debate + 1:30 vote per motion in the Turn 3 Grand Plenary)**:
   - **Two-Sponsor Mandate**: A resolution reaches the floor only if a second realm endorses it.
   - Delegations cast weighted votes (1, 2, or 3 votes). Passed resolutions take statutory effect immediately.
3. **Turn Settlement**: Engine executes consumption, starvation checks, news ticker dispatches.
4. **Turn 3 Finale**: Revelation of secret directives and crowning continental champions.

---

### 5. Domestic State Decrees
| Decree | Cost | Benefit |
| :--- | :--- | :--- |
| **Emergency Grain Rationing (Relief)** | -15 Grain | **+15 Public Vitality** |
| **Stoke Arcane Forges (Fabrication)** | -10 Grain, -10 Silk | **+15 Aether Cores** |
| **Host Grand Cultural Gala (Diplomacy)** | -15 Silk | **+10 Standing, +10 Stability** |
| **Mobilize Civil Guard (Security)** | -10 Cores | **+15 Civil Stability** |
| **Muster Sovereign Regiments (Military)** | -10 Grain, -10 Cores | **+15 Military Power** |

---

### 6. Statutory Resolution Types
- **Emergency Grain Redistribution**: Silos with $>50$ Grain contribute $-10$ Grain; starving realms ($<25$ Grain) receive $+15$ Grain.
- **Continental Wealth Surtax & Embargo**: Chokes trade for the wealthiest plutocrat, inflicting $-15$ Civil Stability.
- **Sovereign Relief Mission**: Sponsoring realm gains $+10$ Diplomatic Standing for international leadership.
- **Frontier Defense & Quarantine Cordon**: Quarantines borders of target realm (blocking external trade) and grants $+10$ Stability.
- **General Sovereign Concordat**: Multilateral treaty providing $+5$ Standing and $+5$ Stability.

---

## 🚀 Terminal Startup Instructions

### 1. Requirements
- Python 3.9+ (Standard macOS / Linux / Windows Python).
- Connect the facilitator laptop and participant smartphones to the same local Wi-Fi router or mobile hotspot (internet connection not required).

### 2. One-Click Launch (Recommended)

From the project directory:

```bash
./run.sh
```

### 3. Manual Launch

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 app.py
```

The server binds to `0.0.0.0:5000` and displays:
```text
=================================================================
  THE SUMMIT OF REALMS - GEOPOLITICAL WORKSHOP PLATFORM
=================================================================
  * Host LAN IP:    http://192.168.1.50:5000
  * Participant UI: http://192.168.1.50:5000
  * Game Overview:  http://192.168.1.50:5000/overview
  * DM Command Deck:http://192.168.1.50:5000/admin
  * Projector View: http://192.168.1.50:5000/projector
  * Local Loopback: http://127.0.0.1:5000
=================================================================
```

---

## 📱 Facilitator, Projector & Student Workflow

1. **Room Projector Setup**:
   - Open `http://localhost:5000/projector` on a second display or projector.
   - The large timer, QR code, and continental standing are immediately visible to all nations.
2. **Facilitator Command**:
   - Open `http://localhost:5000/admin` on the facilitator laptop.
   - Before the session, open **Setup** (`/admin/setup`) to choose the scenario, difficulty, nations, delegates, passcodes and clocks.
   - During play, clocks run out on their own (see *Setting up a summit*); crises from the catalog are optional and manual.
3. **Student Mobile Experience**:
   - Students scan the QR code and select their realm.
   - Use the **persistent bottom navigation bar** to switch between **Overview**, **News**, **Trade**, **Motions**, and **Continent**.
   - Review secret agendas, negotiate treaties, and participate in 60-second Flash Assembly votes.

---

## 🧪 Automated Testing

Run the built-in test suite:

```bash
./venv/bin/python3 -m unittest test_summit.py -v
```


---

## ☁️ Free Internet Hosting (Render.com)

The repo ships a `render.yaml` blueprint; participants join by scanning the QR code on `/admin` or `/projector` (it encodes the public URL automatically).

1. Push the repo to (private) GitHub.
2. Render dashboard → **New → Blueprint** → select the repo → apply.
3. In the service's *Environment* tab set **`ADMIN_PASSCODE`** (facilitator password). `SECRET_KEY` is generated for you.
4. Open `https://<your-service>.onrender.com/admin`, log in, then project `/projector` and show its QR code.

Notes:
- Free instances **sleep after ~15 min idle** (first load takes 30–60 s): open the site 5 minutes before class.
- State lives in `/tmp/summit.db` (ephemeral): a restart/redeploy resets the game. Don't redeploy mid-session.
- Runs as a single gunicorn worker on purpose (timers + SQLite state are per-process).
- Local run is unchanged: `./run.sh`. Env vars: `SECRET_KEY`, `ADMIN_PASSCODE`, `SUMMIT_DB_PATH`, `PUBLIC_URL` (override QR/base URL).
- Realm PINs (`scenario_config.json`) are visible to the facilitator in `/admin`; keep the repo private.

## 📖 Spireopedia & Quiz

- **Spireopedia**: the game's built-in, Wikipedia-style encyclopedia, read in the phone console's **Wiki** tab (no separate site). 22 articles in `lore_articles.json` (`[[slug|label]]` links, infoboxes, contents, search, "what links here"), served as JSON by `/api/wiki`, `/api/wiki/<slug>` and `/api/wiki/search` to logged-in delegations and the facilitator.
- **Quiz** (phone **Quiz** tab): one shared bank in `lore_quiz.json` — every nation gets the same questions. Questions unlock by turn (`turn` field); each nation has **one attempt per question**. Correct: `reward_amount` of `reward_resource`. Wrong: the same resource and amount is lost, and the question locks for that nation.
- Answers never reach the browser before submission: `GET /api/quiz/<realm_id>` (delegation login required) omits `correct_index`/`explanation` for unanswered questions; `POST /api/lore/quiz` checks the answer on the server.
- Every question names the article that contains its answer; `pytest` checks slugs, option counts and links.

## 📜 Motions

Players propose motions from **templates** (`resolution_types` in `scenario_config.json`): each template is shown written out with its plain-language effect ("If passed: …"), ready-made title and terms. The player picks one, edits the title and terms, chooses a target nation if the template needs one (e.g. the Frontier Watch cordon), and optionally limits who may co-sponsor. A motion needs a second nation's co-sponsorship to reach the ballot.

- **Who sees what:** an open motion is visible to everyone, but co-sponsors stay anonymous — other nations only see *that* it has a co-sponsor ("On the ballot"), not who. A motion offered to one nation only ("Who may co-sponsor?") is visible just to the proposer and that nation until it reaches the ballot.
- **Question to the Game Masters** (template `gm_question`, `no_vote: true`): no co-sponsor and no vote. Only the asking nation and the facilitators see it; it appears in the admin's **Resolutions & Questions** tab (with a badge and a chime), where the facilitator answers that nation privately or everyone as a news item.

Decided motions show how each nation voted (votes and nation count). Continental Food Acts A/B are facilitator-only (`player_selectable: false`) and are tabled automatically in Round 3.

## ⚙️ Setting up a summit (`/admin/setup`)

The **Setup** link on the command deck opens one page for everything decided before the session:

1. **Scenario** — *The Great Famine* (the MGV 2026 storyline: Round 2 border incident, Round 3 famine and Continental Food Acts), *Open Summit* (same nations and missions, no scripted crises) or *Armageddon* (the famine storyline plus 3 large disasters and 10 larger small events per turn). Choosing a scenario fills in its suggested event numbers.
2. **Difficulty** — grain eaten per turn and the share of good small events: Gentle 15 / 65 %, Standard 20 / 50 %, Harsh 25 / 35 %.
3. **Nations** — which nations play, delegates per nation (sets seats and how many secret missions it gets), and passcodes (edit one, or **Shuffle passcodes**).
4. **Clocks** — working session, Assembly vote, Grand Plenary debate and vote per motion, and the pause before the next turn.
5. **Random events** — small news items per turn (0–30, default 6), the largest change per small item (1–50, decimals allowed, default 5) and large disasters per turn (0–10). A change made mid-turn applies to the rest of that working session.

**Save settings** changes the running game from now on; **Start a new summit with these settings** begins a fresh game (the old one is kept on the Saves tab). Defaults live in `game_settings_defaults` in `scenario_config.json`.

**When time runs out** a bell sounds on every screen and, with *Move on automatically* ticked (default), the game advances by itself: working session → Assembly vote (or straight to the next turn when no motion is on the ballot) → short pause → next turn … → results after Turn 3. In the Grand Plenary each motion's debate rolls into its vote and then into the next motion. Untick it to only sound the bell and move on by hand.

## 🧭 Running a session: saves, debrief and results

- **Autosave:** every 5 minutes, on the server and in the facilitator's browser (admin → **Saves**). After a server restart, restore the newest copy from "In this browser". **Save now**, **Download save file** and **Load save file** are there too.
- **Reflection debrief:** after concluding the summit, press **Start reflection** on the admin page. The projector shows the 12 reflection questions one at a time (`reflection_questions` in `scenario_config.json`), several with results from the game beside them. **Next question** and **Previous** step through them.
- **Results report:** admin → **Results report** (or **Download results** after the summit) opens a printable page with the outcome, final stats, missions, every trade, every motion and vote, and the full timeline. You can print it, save it as a PDF, or download it as HTML or JSON.
- **Screens stay awake:** the projector, phones and admin page ask the browser not to dim. This works on the hosted (https) site; on a plain-http LAN, browsers don't allow it.

## 🧪 Tests

```bash
venv/bin/pip install -r requirements-dev.txt
venv/bin/python -m playwright install chromium   # once, for the browser tests
venv/bin/python -m pytest -q
```

- `test_summit.py`: engine and API tests.
- `test_e2e.py`: click-through tests. They start the real server with logins enforced and drive a headless browser as phones, the facilitator and the projector, covering trading, motions and voting, private motions and game-master questions, the quiz, the wiki, roster changes, saves, the debrief, the report and the setup screen. They are skipped if Playwright isn't installed.
- `tools/simulate.py`: plays hundreds of complete summits through the real engine with computer-controlled delegations (cooperative or selfish, different quiz skill and difficulty) and prints how often the continent ends stable and how often each mission is met. Use it to check balance after changing numbers in `scenario_config.json`.

## 🗂️ Front-end files

| File | Used by |
| :--- | :--- |
| `static/js/common.js` | every page (sounds, toasts, escaping, keep-screen-awake) |
| `static/js/realm.js` | phone console |
| `static/js/admin.js` | facilitator command deck |
| `static/js/projector.js` | projector screen |
| `static/js/map.js` | projector's animated map (Living Atlas) |
| `static/style.css` | all pages; the header comment explains its sections |
