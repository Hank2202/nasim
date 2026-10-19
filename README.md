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
  - Socioeconomic formulas and mathematical laws cheat sheet (starvation thresholds, technological efficiency, the wealthiest nation's bonus vote).
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
  - **Per-Turn Consumption**: 20 Grain per turn at Standard difficulty (15 Gentle, 25 Harsh).
  - **The Starvation Threshold**: If Grain drops to $\le 0$, automatic penalty of -25 Public Vitality and -20 Civil Stability.
  - **Technological Efficiency**: If Aether Cores $\ge 75$, permanently cuts grain consumption by 25% (-15 instead of -20).
  - **Voting weights**: fixed per nation as in the facilitator notes (Solaris 3, Umbra 1, the others 2), plus +1 for the single wealthiest nation (Grain + Cores + Silk) while it stays the wealthiest.
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
- **Frontier Defense & Quarantine Cordon**: the target nation gains $+10$ Stability, and plague, border-surge and tsunami disasters hit it 50–70 % less hard. Trade is not affected.
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
- State lives in `/tmp/summit.db` (ephemeral), and every server start begins a fresh game anyway (see below). Don't redeploy mid-session.
- Runs as a single gunicorn worker on purpose (timers + SQLite state are per-process).
- Local run is unchanged: `./run.sh`. Env vars: `SECRET_KEY`, `ADMIN_PASSCODE`, `SUMMIT_DB_PATH`, `PUBLIC_URL` (override QR/base URL), `FRESH_START=0` (keep the game across restarts).
- Realm PINs (`scenario_config.json`) are visible to the facilitator in `/admin`; keep the repo private.

## 📖 Spireopedia & Quiz

- **Spireopedia**: the game's built-in, Wikipedia-style encyclopedia, read in the phone console's **Wiki** tab (no separate site). 22 articles in `lore_articles.json` (`[[slug|label]]` links, infoboxes, contents, search, "what links here"), served as JSON by `/api/wiki`, `/api/wiki/<slug>` and `/api/wiki/search` to logged-in delegations and the facilitator.
- **Quiz** (phone **Quiz** tab) is a **timed run, one question at a time**:
  1. The nation sees only the **stake** and the topic, and presses **Start the clock** when it is ready (no further dialog: the next question never starts by itself). The stake is **random for every question, 1 to 9 Grain, Cores or Silk (average 5)**; `quiz.stake_min` / `stake_max` in `scenario_config.json`.
  2. The clock starts on the server (`quiz_seconds`, default 15, set on the setup screen). The phone shows the question, the shuffled options and a countdown. Tapping an option answers at once. Leaving the page does not stop the clock; a question that runs out of time counts as wrong (the server settles it on the next poll).
  3. Correct: the stake is added in the question's resource. Wrong or out of time: **the same resource and amount is lost** and the question is locked. The result shows the explanation and a link to the article; "Next question" leads back to the start card with the next stake.
  - The bank (`lore_quiz.json`) has 62 questions: 32 `standard` and 30 `hard` ones that ask for details (numbers, names, who did what). Every nation gets its questions in its **own random order** (a refresh shows the same next question and stake until it is started). A delegation shares one open question, so teammates see the same clock.
  - There is no pointer to the article while a question is open, and the options are shuffled for every question.
  - **News:** answers are not announced one by one. Every five minutes (and at the end of each turn and of the summit) one item sums up the quiz ("3 of 6 nations answered 11 questions: 8 correct, 3 wrong…"), without names or resources. The results report still lists every nation's correct and wrong answers.
  - API: `GET /api/quiz/<realm_id>` (progress, the open question, what comes next, history), `POST /api/quiz/start` (start the next question), `POST /api/lore/quiz` (answer; the correct answer is only revealed afterwards). `pytest` checks slugs, option counts and links.

## 📜 Motions

Players propose motions from **templates** (`resolution_types` in `scenario_config.json`). They pick one, **set its numbers**, rewrite the title and terms in their own words and optionally limit who may co-sponsor. A motion needs a second nation's co-sponsorship to reach the ballot.

**Motions apply themselves.** A motion carries structured effect lines (`motions.py`), and the sentence under "If passed" is generated from those lines by the server (`POST /api/proposal/preview` shows it live while the player edits). When the motion passes, the game carries the lines out and records what really happened ("Carried out: Sylvan −12 Grain; Umbral Enclave +12 Grain"), which also goes into the news and the report. The free-text terms are for explaining the deal; the facilitator no longer carries anything out by hand.

| Template | What the player sets | Effect |
| :--- | :--- | :--- |
| Resource Redistribution | resource, upper and lower limit, amount given and received | nations above the upper limit give; what is collected goes to nations below the lower one. Nothing is created |
| Sanction or Embargo | the nation (or "the richest / poorest / strongest / weakest"), what it loses, how much | the nation loses up to that amount |
| Resource Pact | up to 3 lines: transfer (who gives, how much, who shares it) or penalty | exactly the lines; value-conserving transfers and fines |
| Open Motion (no template) | free text only | nothing happens automatically: if it passes, it waits in the facilitator's **Resolutions & Questions** tab until they carry it out (bulk editor, modifiers or in the room) and mark it as carried out |
| Sovereign Relief Mission, Concordat | nothing (fixed) | +10 Standing, or +5 Standing and +5 Stability, for the proposer |
| Frontier Cordon | the nation | +10 Stability, shielded from plague, border surges and tsunamis, and a stronger defence in battle |
| Question to the Game Masters | the text | the facilitators answer it for everyone |

Players cannot make value out of nothing: transfers only move what exists, and fixed templates are the only ones that create anything. **There is no cap on the amounts a motion may name**, but the automatic part takes at most what a nation really has, and receivers only get what was actually taken (a pact asking Sylvan for 500 Grain moves the 100 it has). Inactive nations are skipped when a motion passes.

- **Who sees what:** an open motion is visible to everyone, but co-sponsors stay anonymous: other nations only see *that* it has a co-sponsor ("On the ballot"). A motion offered to one nation only ("Who may co-sponsor?") is visible just to the proposer and that nation until it reaches the ballot.
- **Question to the Game Masters** (`gm_question`): like any motion it needs a co-sponsor and a passing vote. Once passed it appears in the admin's **Resolutions & Questions** tab, the facilitator types an answer, and everyone sees it on the motion card and as news. Questions don't count as resolutions for missions.
- **No limit** on how many motions a nation may table.
- The facilitator sees the same "If passed" text on every motion card and a reference list of all templates at the bottom of the Resolutions tab. Continental Food Acts A/B are facilitator-only and are tabled automatically in Round 3.

## 🛠️ Facilitator corrections: modifiers and the action log

Both live in the **Resource Overrides** tab.

- **Modifiers of each nation:** one card per nation lists the automatic modifiers with their reasons (+1 vote for the richest, Grain use −25 % with Efficient Cores, +8 % defence while cordoned, home-ground defence, strike, starvation) and lets you set adjustments by hand, for example when the players rewrote a motion: **extra Assembly votes** (−3 to +5), **Grain eaten each turn** (−100 % to +200 %), **army strength in every battle** and **extra strength when attacked** (−80 % to +200 %), and the flags *Cordoned*, *General strike* and *Efficient Cores* (switching Efficient Cores off stays off even with 75+ Cores). The war adjustments are never shown to the players, and the scouts never reveal them. API: `GET/POST /api/admin/modifiers`.
- **Action log:** every request that changed a nation's numbers (your own edits, trades, quiz answers, battles, motion effects, events) is listed with what changed ("Umbral Enclave: Grain 40 → 65"). **Reverse this change** (with a confirmation) applies the opposite change, so later changes to the same nation are kept. Battles and decided motions stay on record; only their resource changes are undone. Ending a turn, concluding the summit and crisis rounds are listed but cannot be reversed here. A new game clears the log. API: `GET /api/admin/journal`, `POST /api/admin/journal/undo`.

## ⚔️ War

From the turn set on the setup screen (Turn 2 by default) a nation can attack another from the **War room** on the Realm tab, once per turn (setting). No nation can be attacked more than twice a turn. There are **two ways to attack** (`battle.modes`):

- **Siege** (the normal way): announced to everyone the moment it is ordered (news, a countdown on the projector and on every phone, an alarm on the target's phone, a marching banner on the map). The army arrives after **2 minutes of working-session time** (`seconds`; a paused clock pauses the march), and the battle is fought then with the numbers of that moment, so the defender can trade for Grain, steady its people or raise its army. Supplies (10 Grain) are paid at once. An army still on the road when the turn ends arrives first. The facilitator can *Arrive now* or *Call back* (supplies returned) from the Events tab.
- **Surprise attack**: fought at once and nobody is warned. The attacker gets +8 % strength (the defender is caught unprepared) but pays heavily: double supplies (20 Grain), **15 Standing and 8 Stability extra** on top of the usual loss of Standing, and the defender gains 5 Standing if it holds.

**Strength = Military × readiness × (1 + ground, weather and the facilitators' adjustments + luck)**

- **Readiness** (about 0.35 to 1.9) multiplies the army by how ready the nation is: Stability (weight 0.22), Grain (0.20), Cores (0.14), Vitality (0.10), Standing (0.06) and Silk (0.04). Each value's pull is `sign(v−50)·(|v−50|/50)^1.6`, so values near 50 hardly matter and the effect grows quickly with the distance from 50. A starving, unstable nation fights far worse; a fed, calm one far better.
- **Ground and weather** (a few percent): the defender's terrain (mountains +10 %, islands +8 %, open fields −4 to −5 % …), a cordon (+8 %), and the weather of the turn (rolled when the turn starts and shown to everyone: rain and storms hamper attackers, fog and heat hurt both, a tailwind or a moonless night helps attackers). **Luck** is up to ±12 % per side, well under the readiness range, and is **never shown to the players** (only the facilitator's war log lists it).
- **Result** by the margin |A−D|/(A+D): stalemate (< 0.04), narrow, normal, crushing (> 0.40). The loser loses soldiers (8 % to 40 % of its Military), Stability (3 to 20) and Vitality, and a share (5 % to 35 %) of its Grain, Cores and Silk, of which the winner keeps 75 %. The winner also loses a few soldiers and 2 Stability. The attacker always loses 6 Standing (10 for a crushing win over a weak nation, and for a defeat), the defender gains 3 if it wins. Supplies cost the attacker 10 Grain.
- **Fog of war:** before attacking, the scouts give a blurred estimate of the odds ("Favourable"…) and a list of **modifiers** (readiness factors of both sides, the defender's home ground, a cordon), the weather in words, and the target's Military tier. How much the scouts find out depends on the attacker's resources: **wealth (Grain + Cores + Silk) decides how many modifiers are revealed** (about one per 28; the biggest first) and **Silk and Cores decide how accurate they are** (rough words such as "slightly helps" for poor nations, ranges such as "between +5% and +20%" for fair ones, "about +12%" for rich ones; never exact, and your own side is known better than the enemy's). The same seed gives the same report, so asking again learns nothing. The random roll and the facilitators' adjustments are never revealed. After the battle both nations see their own losses and spoils and the same kind of scouted modifier list; everyone sees the outcome and the spoils. Tune in `battle.intel`.
- **Show:** the battle is announced in the news, sounds a war horn, takes over the projector's *Realm in Focus* panel with an animation (two armies of soldiers march onto a field drawn from the battle's ground and weather, clash under the nations' banners, soldiers fall in proportion to the losses, the line of battle shifts towards the weaker side, the beaten army routs and the winner cheers; then the result, spoils and losses appear), draws a burning arc between the two capitals on the map, and opens as an animation on the two nations' phones. The facilitator's **War log** (Events tab) shows both sides' numbers.
- Everything is tunable in the `battle` section of `scenario_config.json` (weights, curve, luck, terrain, weather table, plunder). Attacks can be switched off on the setup screen. `tools/simulate.py --war` shows what attacks do to the continent: a peaceful, cooperative group wins as before; opportunistic attackers (3 battles a game) cut the share of "Stable Continent" endings sharply.

## 👥 Fewer than six nations

Untick a nation on the setup screen and the game adapts:

- **Mission targets scale** with the number of nations playing (`engine.scaled_targets`): Val-Khor's "4 of 6 nations reach 60 Cores" and Solaris' "resolutions backed by 4 nations" become 3 of 5; Aquila's "trade with 4 of the other 5" becomes 3 of 4. With six nations the numbers are exactly the facilitator notes'.
- **Every delegate keeps a secret mission.** A mission about a nation that is not playing switches to a stand-in version (`stand_in` in `scenario_config.json`): without Aethelgard, Sylvan's "Independent Defense" becomes "don't buy Military from anyone" and Val-Khor's parity mission is measured against the strongest army; without Val-Khor, Solaris and Aethelgard check any rival instead. Without Solaris, Umbra plays "Sovereign Independence". The setup screen shows each nation's number of secret missions.
- **Which nation to leave out:** Umbra (1 delegate) or Aquila (2) change the least: no other nation's missions depend on them. Without Sylvan food is tighter (46 Grain per nation at the start instead of 55). `venv/bin/python tools/simulate.py --rosters` plays every 5-nation roster: with cooperative play all of them end stable as often as the full game.
- Food Act B's quota scales too (10 Cores × (nations − 1)).

## ⚙️ Setting up a summit (`/admin/setup`)

Logging in before a game has started opens this page first; afterwards the **Setup** banner at the top of the command deck (and the header link) leads back to it. The facilitator login lasts 24 hours in that browser; **Lock** logs out. The page covers everything decided before the session:

1. **Scenario** — *The Great Famine* (the MGV 2026 storyline: Round 2 border incident, Round 3 famine and Continental Food Acts), *Open Summit* (same nations and missions, no scripted crises) or *Armageddon* (the famine storyline plus 3 large disasters and 10 larger small events per turn). Choosing a scenario fills in its suggested event numbers.
2. **Difficulty** — grain eaten per turn and the share of good small events: Gentle 15 / 65 %, Standard 20 / 50 %, Harsh 25 / 35 %. With careful sharing a group can win Gentle without touching the quiz; Standard needs good cooperation and some success in the quiz; Harsh needs a strong quiz as well.
3. **Nations** — which nations play, **how hard each nation is to play** (Easy, Medium or Hard with the reason; see below), delegates per nation (sets seats and how many secret missions it gets), and passcodes (edit one, or **Shuffle passcodes**).
4. **Clocks and limits** — working session, Assembly vote, Grand Plenary debate and vote per motion, the pause before the next turn and the time per quiz question.
5. **War** — allow attacks, the turn they unlock in and how many attacks a nation may make per turn.
6. **Random events** — small news items per turn (0–30, default 6), the largest change per small item (1–50, decimals allowed, default 5) and large disasters per turn (0–10). A change made mid-turn applies to the rest of that working session.

**Save settings** changes the running game from now on; **Start a new summit with these settings** begins a fresh game (the old one is kept on the Saves tab). Defaults live in `game_settings_defaults` in `scenario_config.json`.

**When time runs out** a bell sounds on every screen and, with *Move on automatically* ticked (default), the game advances by itself: working session → Assembly vote (or straight to the next turn when no motion is on the ballot) → short pause → next turn … → results after Turn 3. In the Grand Plenary each motion's debate rolls into its vote and then into the next motion. Untick it to only sound the bell and move on by hand.

## 🎚️ Easy and hard nations

Every nation is rated Easy ★, Medium ★★ or Hard ★★★ with a short reason (`difficulty` 1–3 and `difficulty_note` in `scenario_config.json`; the reasons never mention secret missions because the lobby is public). The rating is shown on the lobby cards, on the setup screen, in the Guide and on each nation's own phone, so the facilitator can give the hard nations to experienced participants and the easy ones to newcomers. Easy: **Solaris** (rich and respected; the challenge is coordinating 4 delegates) and **Aethelgard** (the strongest army and a calm people). Medium: **Aquila** (an easy public mission, but "wealthiest by 25" means hoarding while trading with everyone). Hard: **Umbra** (one delegate, one vote, the lowest Standing), **Sylvan** (everyone needs its grain, weak army) and **Val-Khor** (starts with 30 Grain and competing goals). `venv/bin/python tools/simulate.py --nations` plays many games and prints the share of its missions each nation meets.

## 🧭 Running a session: saves, debrief and results

- **Clock console** (Pacing tab; the header clock opens it): one set of controls for whichever clock the phase has: the working session, the pause before a turn, the Grand Plenary debate, the Assembly vote, and, between turns and after the summit, a free countdown for a break or the debrief. Type minutes and seconds, nudge by ±10 s, ±1 min, ±5 min, pause, resume or reset to the default length.
- **Resources** (Resource Overrides tab): change several nations and several resources at once (add, take away or set to an exact number, typed), see exactly what each nation would end up with, and optionally tell the nations (news and a sound). Silent changes are written to the results report. In the table every value can also be typed (Enter, then confirm) or nudged with +/−.
- **Confirmations:** almost every action asks first, on the facilitator's deck and on the phones (decrees, offers, accepting a trade, motions, co-sponsoring, votes, taking a quiz question, attacking). A dialog ignores clicks and key presses for a third of a second after it opens, so the key or tap that opened it cannot also answer it.

- **Every server start is a fresh game** straight from `scenario_config.json` (settings, roster, delegates and passcodes), so config changes always take effect and the facilitator lands on the setup screen. A game that was under way is kept on the Saves tab as "Before server restart" (restore it if the restart was an accident). Set `FRESH_START=0` to keep the game across restarts instead. For gunicorn (Render) this runs once at server start from `gunicorn.conf.py`, never when a worker restarts.
- **Logins belong to one game:** a new game (server start, Reset, or "Start a new summit") logs every phone out; open phones return to the passcode screen by themselves. The facilitator login is kept.
- **No stale files:** pages and scripts are sent with `Cache-Control: no-cache` (the browser checks for a newer version every time) and game state with `no-store`.
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
