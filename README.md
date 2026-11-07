# The Summit of Realms - Live Geopolitical Strategy Simulation Platform

A lightweight, real-time web application built for live educational simulations. It runs locally on a facilitator's laptop (`0.0.0.0:5000`) and serves real-time responsive interfaces to students' smartphones and room projectors over a local Wi-Fi network with **zero external internet required**.

---

## 🌟 Key Features

- **Two difficulty settings**: the *game complexity* (the **Full game**, or a **Simplified** game with ready-made motions and no quiz or war) and the *scenario* (Open summit, The Great Famine, Armageddon). See [Two difficulty settings](#-two-difficulty-settings).
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
- **Join page (`/`)**: every nation fits on the first screen of a phone. Tap the nation, type the passcode. A phone that is already in a delegation gets a one-tap way back, and a full delegation says what to do. Printable **passcode cards** (`/admin/cards`) give each table a QR code that opens its nation's login.
- **Phone console (`/realm/<id>`)**, built so the game's complexity is the only thing that is hard:
  - A card on top says in words what is going on and what comes next: about to begin, working session, clock paused, vote.
  - **Six tabs**: **Realm** (your numbers, goals, decrees, war room), **World** (news, and estimates of the other nations), **Trade**, **Motions**, **Wiki** and (full game) **Quiz**. Badges say where something waits for you.
  - Tap any of your numbers to see what it does. The **?** button explains how a turn goes and holds the Guide, the sound switch and the way out.
  - What needs an answer comes first: offers to you sit above the trade form, the motions on the floor above the proposal form, and a vote appears on top of every tab (and closes the wiki).
  - Numbers that change show their change (−12) where they stand; decrees you cannot pay for say so before you tap.
- **Random events**:
  - During each working session the game posts small news items (default 6 per turn, 50 different ones, good and bad) that hit one nation. Each resource an item touches moves by a random amount between 0 and the largest change set on the setup screen (default 5; decimals allowed), at least 1. The share of good news is set by the scenario.
  - **Large disasters** (12: earthquake, tsunami, drought, blight, reactor breach, plague, revolt, border surge, dragon raid, great storm, tornado swarm, meteor shower; usually −10 to −25) strike at random only when *Large disasters per turn* is above 0 — the Armageddon scenario sets 3. They show on the projector map.
  - The famine storyline's crises (Round 2 border incident, Round 3 Great Famine) are built in. Catalog crises can also be triggered by hand (**⚡ Trigger Next Recommended Crisis**, the catalog dropdown), and there are **Good news now**, **Bad news now** and **Random disaster now** buttons.
- **Facilitator Command Deck (`/admin`)**: a panel that stays in sight on every tab says what is going on, what happens next and offers the buttons for it (Start Turn 1, Pause, Convene the Assembly, who still has to vote…). Before the first turn a checklist walks through the room: game, projector, passcodes, start. Tabs: **Run the game**, **Motions**, **Events**, **Nations' numbers**, **Players & passcodes**, **Saves**. It works on a phone too.
- **Hidden Socioeconomic Engine**:
  - **Per-Turn Consumption**: set by the scenario: 20 Grain per turn in the Great Famine and Armageddon, 15 in the Open summit (and any number you type on the setup screen).
  - **The Starvation Threshold**: If Grain drops to $\le 0$, automatic penalty of -25 Public Vitality and -20 Civil Stability.
  - **Technological Efficiency**: If Aether Cores $\ge 75$, permanently cuts grain consumption by 25% (-15 instead of -20).
  - **Voting weights**: fixed per nation as in the facilitator notes (Solaris 3, Umbra 1, the others 2), plus +1 for the single wealthiest nation (Grain + Cores + Silk) while it stays the wealthiest.
- **Nothing gets lost**: the game lives in SQLite (`summit.db`) and is saved every 5 minutes, at the start of every turn and every minute in the facilitator's browser. After a crash or restart the deck offers to bring the game back, and the phones reconnect by themselves. See [Saves](#-saves-what-happens-when-the-server-stops).

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
- **Assembly Votes**: fixed per nation (Solaris 3, Umbra 1, the others 2), plus **+1** for the single wealthiest nation (Grain + Cores + Silk) while it stays the wealthiest.
- **Grain Consumption & Starvation**:
  - Baseline: **-20 Grain** consumed every operational turn in the Great Famine (the scenario sets this number).
  - With **Technological Efficiency** (Cores $\ge 75$): Grain consumption drops permanently by 25% (**-15 Grain**).
  - **Starvation Penalty**: If Grain drops to $\le 0 \implies$ immediate penalty of **-25 Vitality** and **-20 Stability** (only the Stability in the Simplified game, which has no Vitality).

---

### 4. Turn Cadence & Workshop Flow (3 Turns Total)
1. **Working & Bilateral Trade Session (default 20:00, set on the setup screen)**:
   - Roam the room freely for face-to-face bilateral diplomacy.
   - Execute instant atomic P2P trades (Grain, Cores, Silk, Military Power).
   - Enact internal state decrees (relief, forges, galas, security, mustering).
   - Full game: read the Spireopedia and answer the shared quiz (a random stake of 1 to 9 of a resource is won or lost, and a wrong answer locks the question).
   - Author statutory resolutions for the Plenary docket (Simplified game: table ready-made ones).
2. **Plenary Floor Debate & Assembly vote (default 3:00 vote in Turns 1–2; 5:00 debate + 1:30 vote per motion in the Turn 3 Grand Plenary of the full game; the Simplified game has the 3:00 vote in every turn)**:
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
See [Motions](#-motions) for the full game's templates and [Two difficulty settings](#-two-difficulty-settings) for the ready-made motions of the Simplified game.

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
  * Facilitator passcode: admin2026
=================================================================
```

The facilitator passcode comes from the `ADMIN_PASSCODE` environment variable, or else from `simulation_settings.admin_passcode` in `scenario_config.json`.

---

## 📱 Facilitator, Projector & Student Workflow

1. **Facilitator**:
   - Open `http://localhost:5000/admin` on the facilitator laptop and log in. Before a game this opens **Setup**: choose the game complexity, the scenario and who plays, then **Continue to the command deck**.
   - The deck's **Before you start** checklist does the rest: open the projector, hand out the passcodes (print the **passcode cards**, or read them from the list), and press **Start Turn 1** when everyone is in.
   - From then on the panel on top always says what is happening and what comes next. Clocks run out on their own (see *Setting up a summit*); crises from the catalog are optional and manual.
2. **Projector**: `http://localhost:5000/projector` on a second display. Its **Join QR** button shows the code for the phones.
3. **Players**: scan the QR code (or the code on their nation's card), tap their nation and type its passcode. Everyone in a delegation uses the same passcode. A short card on the phone explains the rest, and the **?** button is always there.

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
- Realm PINs (`scenario_config.json`) are visible to the facilitator in `/admin`; keep the repo private. The defaults (1001, 1002, …) are easy to guess, so the deck suggests shuffling them before the game.

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

This section describes the full game; the Simplified game has [ready-made motions](#-two-difficulty-settings) instead. Players propose motions from **templates** (`resolution_types` in `scenario_config.json`). They pick one, **set its numbers**, rewrite the title and terms in their own words and optionally limit who may co-sponsor. A motion needs a second nation's co-sponsorship to reach the ballot.

**Motions apply themselves.** A motion carries structured effect lines (`motions.py`), and the sentence under "If passed" is generated from those lines by the server (`POST /api/proposal/preview` shows it live while the player edits). When the motion passes, the game carries the lines out and records what really happened ("Carried out: Sylvan −12 Grain; Umbral Enclave +12 Grain"), which also goes into the news and the report. The free-text terms are for explaining the deal; the facilitator no longer carries anything out by hand.

| Template | What the player sets | Effect |
| :--- | :--- | :--- |
| Resource Redistribution | resource, upper and lower limit, amount given and received | nations above the upper limit give; what is collected goes to nations below the lower one. Nothing is created |
| Sanction or Embargo | the nation (or "the richest / poorest / strongest / weakest"), what it loses, how much | the nation loses up to that amount |
| Resource Pact | up to 3 lines: transfer (who gives, how much, who shares it) or penalty | exactly the lines; value-conserving transfers and fines |
| Open Motion (no template) | free text only | nothing happens automatically: if it passes, it waits in the facilitator's **Motions** tab until they carry it out (bulk editor, modifiers or in the room) and mark it as carried out |
| Sovereign Relief Mission, Concordat | nothing (fixed) | +10 Standing, or +5 Standing and +5 Stability, for the proposer |
| Frontier Cordon | the nation | +10 Stability, shielded from plague, border surges and tsunamis, and a stronger defence in battle |
| Question to the Game Masters | the text | the facilitators answer it for everyone |

Players cannot make value out of nothing: transfers only move what exists, and fixed templates are the only ones that create anything. **There is no cap on the amounts a motion may name**, but the automatic part takes at most what a nation really has, and receivers only get what was actually taken (a pact asking Sylvan for 500 Grain moves the 100 it has). Inactive nations are skipped when a motion passes.

- **Who sees what:** an open motion is visible to everyone, but co-sponsors stay anonymous: other nations only see *that* it has a co-sponsor ("On the ballot"). A motion offered to one nation only ("Who may co-sponsor?") is visible just to the proposer and that nation until it reaches the ballot.
- **Question to the Game Masters** (`gm_question`): like any motion it needs a co-sponsor and a passing vote. Once passed it appears in the deck's **Motions** tab (and the deck's top panel says so), the facilitator types an answer, and everyone sees it on the motion card and as news. Questions don't count as resolutions for missions.
- **No limit** on how many motions a nation may table.
- The facilitator sees the same "If passed" text on every motion card and a reference list of all templates at the bottom of the Motions tab. Continental Food Acts A/B are facilitator-only and are tabled automatically in Round 3.

## 🛠️ Facilitator corrections: modifiers and the action log

Both live in the **Nations' numbers** tab.

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

Logging in before a game has started opens this page first; afterwards the **Setup** link at the top of the command deck leads back to it. The facilitator login lasts 24 hours in that browser; **Log out** ends it. Steps 1 to 3 are all a facilitator has to decide; the rest stays closed under *Fine-tuning* with its values in the title. The nations table applies at once; the other settings wait for **Save settings**, and the page says so when something is not saved yet. The page covers:

0. **Language of the game** — English or Čeština, for every screen that has not chosen its own (see [Languages](#-languages-english-and-czech)).
1. **Game complexity** — the Full game or the Simplified game (see [Two difficulty settings](#-two-difficulty-settings)). Fields for mechanics the chosen game does not have disappear from this page.
2. **Scenario** — *Open summit* (no scripted crises), *The Great Famine* (the MGV 2026 storyline: Round 2 border incident, Round 3 famine and Continental Food Acts) or *Armageddon* (the famine storyline plus 3 large disasters and 10 larger small events per turn). Choosing a scenario fills in its numbers under *Scenario numbers*.
3. **Nations** — which nations play, **how hard each nation is to play** (Easy, Medium or Hard with the reason; see below), delegates per nation (sets the seats and, in the full game, how many secret missions it gets), and passcodes (edit one, or **Shuffle passcodes**).
Under *Fine-tuning*:

- **Clocks** — working session, Assembly vote, the pause before the next turn and, in the full game, the Grand Plenary debate and vote per motion and the time per quiz question.
- **War** (full game) — allow attacks, the turn they unlock in and how many attacks a nation may make per turn.
- **Scenario numbers** — Grain each nation eats per turn, the share of good news, small news items per turn (0–30), the largest change per small item (1–50, decimals allowed) and large disasters per turn (0–10). This is where to make a scenario gentler or harsher: 15 Grain and 65 % good news are the old *Gentle*, 25 Grain and 35 % the old *Harsh*. A change made mid-turn applies to the rest of that working session.

**Save settings** changes the running game from now on, except its complexity: before play has begun a new complexity applies at once (phones follow by themselves), afterwards it waits for the next new summit. Once a game is under way the page also offers **Start a new summit with these settings**, which begins a fresh game and keeps the nations and passcodes (the old game stays on the Saves tab). Defaults live in `game_settings_defaults` in `scenario_config.json`.

**When time runs out** a bell sounds on every screen and, with *Move on automatically* ticked (default), the game advances by itself: working session → Assembly vote (or straight to the next turn when no motion is on the ballot) → short pause → next turn … → results after Turn 3. In the Grand Plenary each motion's debate rolls into its vote and then into the next motion. Untick it to only sound the bell and move on by hand.

## 🌐 Languages: English and Czech

The whole game speaks English or Czech: phones, the command deck, the setup screen, the projector (map labels included), the Guide, the passcode cards, the results report, every news item and message, the secret missions, the quiz and the Spireopedia.

- **For everyone:** choose *Language of the game* at the top of the setup screen and save. Open screens switch by themselves. English is the default (`game_settings_defaults.language` in `scenario_config.json`). The choice survives a server restart and is not changed by restoring a save.
- **For one device:** the *English · Čeština* switch on the join page, in a phone's `?` help, in the page header (deck, setup, Guide) and in the projector's settings. A device that has chosen keeps its language until it chooses again; the others follow the game. Changing the game's language on the setup screen clears that browser's own choice, so the facilitator sees what they chose.
- Names are Czech too: *Sylvanský konkordát, Železný Val-Khor, Solariská nadvláda, Umbrijská enkláva, Aquilská námořní liga, Aethelgardské dominium*, towns such as *Kořenov, Lucernopád, Slaná Brána*, the *Mlžná propast* and *Velkohvozd*; the Spireopedia is the *Věžopedie* and years are counted *PK* (po Konvergenci). Invented personal names that mean nothing in English (Hadrek Vorn, Maren Ostrel) stay as they are; *Ilvara Sunmaker* becomes *Ilvara Slunotvůrkyně*. The resources are *obilí, jádra, hedvábí, vojsko, vitalita, reputace, stabilita*; nations are *státy*, motions *návrhy*, the Assembly *Shromáždění*, the Grand Plenary *Velké plénum*, as in the facilitator notes.

**How it works.** The code, the database and save files stay in English. Texts are translated on their way to a screen, from catalogues of “English text → translation” in `translations/cs/`:

| File | What | Sent to browsers? |
| :--- | :--- | :--- |
| `config.json` | nations, missions (secret ones too), motions, events, scenarios | no |
| `messages.json` | everything the server says: news, results, errors, mission checks | no |
| `pages.json` | the text of the pages | no |
| `quiz.json` | questions, options and explanations | no |
| `public.json` | what the page scripts write on phones and the projector | yes, to everyone |
| `deck.json` | what the command deck's scripts write | only to the facilitator |
| `lore_articles.json` | the Czech Spireopedia (same slugs and links as `lore_articles.json`) | as articles, like the English |

`i18n.py` translates pages and game data on the server (`app.py`, after each request); `static/js/i18n.js` translates what page scripts write, as they write it. Both use the same rules. A catalogue key can hold placeholders: `{n}`, `{n2}`… match a number, `{amount}` a number with a resource (“+5 Grain”), `{name}` or `{…_name}` a name in capitals, any other `{word}` free text within one sentence. What a placeholder matched is translated as well, and `{n:hlas|hlasy|hlasů}` picks the Czech plural. Symbols around a text (arrows, ticks, a colon) need no entry of their own, and a long text is translated sentence by sentence or around ` · `, `:`, `,` when the whole is not in the catalogue. **Never put a secret in `public.json` or `deck.json`**: `test_i18n.py` checks that no secret mission and no quiz answer is in them.

To change a Czech text, edit its value in `translations/cs/`; the server picks the change up without a restart. When you add English text to the game, add its Czech too (the tests list missing quiz and mission translations; for the screens, play a game in Czech and look for English). Another language is another folder next to `cs` plus its name in `LANGUAGES` in `i18n.py`.

## 🧩 Two difficulty settings

Difficulty is two independent choices on the setup screen. Any complexity can be played with any scenario, and the setup screen, phones, projector, Guide and report all follow the choice.

### Game complexity: how much there is to learn and to do

| | **Full game** | **Simplified** |
| :--- | :--- | :--- |
| Motions | written by the players: templates, their own wording and numbers, resource pacts, open motions, questions to the game masters | six **ready-made** motions: pick one, set the amount where it has one, table it. No wording to write, no nation to choose, and every effect is automatic, so the facilitator never carries anything out |
| Quiz | the timed Spireopedia quiz wins and loses resources | **none**: every nation starts with **+20 Grain, +10 Cores, +10 Silk** instead |
| War | sieges, surprise attacks, scouts, fog of war | none |
| Secret missions | one per delegate (up to 4) | **one per nation**, a clear goal about the nation itself (so it works whoever else is playing) |
| Assembly | quick vote in Turns 1–2, Grand Plenary in Turn 3 (a debate and a vote per motion) | the **same single vote** at the end of every turn |
| Vitality | a value to watch, with the Grain Rationing decree | not played: no bar, no decree, not in the news |
| Help on the phone | none | how far the Grain lasts ("15 Grain short for the 2 meals left"), whether each mission is **on track** right now, and **exactly how the continent is judged** (in the `?` help, on the Stability, Standing and Grain numbers and in the Guide) |
| How the continent is judged | the players find out at the end | stated in advance: a **stable continent** needs no nation out of Grain at the end, every nation at 50 Stability or more and an average Standing of 50 or more, and no nation's Stability ever at 0; a **fragile peace** allows one nation out of Grain; two or more, or a Stability of 0, mean a **continental crisis** |

The Spireopedia stays available in the Wiki tab of the Simplified game for anyone curious, but nothing depends on it. Trading, decrees, co-sponsors and weighted votes are the same in both games, and so are the famine, the verdict and the debrief. The complexity is stored in `complexities` in `scenario_config.json`, one switch per mechanic, and a game keeps the complexity it was dealt with (`meta.complexity`).

**The ready-made motions** (`simple_motions` in `scenario_config.json`):

| Motion | The amount | If it passes |
| :--- | :--- | :--- |
| 🌾 Share the Grain | 5–30, default 10 | every nation above 50 Grain gives the amount; nations below 25 share what is collected |
| ⚙️ Modernisation Fund | 5–30, default 10 | every nation above 70 Cores gives the amount; nations below 60 share what is collected |
| 🤲 Plea for Aid | 5–20, default 5 | every other nation gives the amount of Grain to the nation that tabled it |
| ⚖️ Sanction the Richest | 5–30, default 10 | the richest nation at the moment of the vote loses that much Stability |
| 🕊️ Relief Mission | none | the nation that tabled it gains 10 Standing |
| 🛡️ Guard Our Borders | none | the nation that tabled it gains 10 Stability and is shielded from plague, border surges and tsunamis |

**The one secret mission per nation** (`simple_secret` per nation): Sylvan *Independent Security* (40 Military, none bought from Aethelgard), Val-Khor *Workers' Bread* (30 Grain), Solaris *Domestic Prosperity* (50 Silk), Umbra *Sovereign Independence* (60 Cores and 60 Stability), Aquila *Indispensable Partner* (trade with 4 of the other 5), Aethelgard *Strategic Reserves* (35 Grain and 35 Cores).

**How the starting bonus was set.** `tools/simulate.py` measured what the quiz really pays: a nation answering well nets about +9 Grain, +11 Cores and +11 Silk over a game. Cores and Silk take that amount. Grain is what decides the game, so its bonus was set by arithmetic and simulation: at +10 the food left after the meals and the famine (50) cannot cover what the secret missions ask (69), at +15 it just can, and +20 leaves 110, room for bad news and human mistakes. A test plays a complete game that meets all twelve missions.

### Scenario: how hard the world is

| Scenario | Rated | Storyline | Grain per turn | Good news | Small events per turn (largest change) | Large disasters per turn |
| :--- | :--- | :--- | ---: | ---: | ---: | ---: |
| Open summit | Easy ★ | none | 15 | 65 % | 6 (5) | 0 |
| The Great Famine (MGV 2026) | Standard ★★ | border incident, Great Famine, Food Acts | 20 | 50 % | 6 (5) | 0 |
| Armageddon | Hard ★★★ | the same | 20 | 50 % | 10 (8) | 3 |

The numbers live in `scenarios` in `scenario_config.json` and are filled in on the setup screen, where they can be changed for one game.

### What the two settings do together

Computer-controlled delegations, 40 games per row, no attacks in either game so the rows compare fairly (`venv/bin/python tools/simulate.py --simplified`). These are estimates of what sensible play can reach, not predictions of a real group, and nobody has played the Simplified game with real people yet.

| Complexity and scenario | Delegations | Stable | Fragile | Crisis | Missions met |
| :--- | :--- | ---: | ---: | ---: | ---: |
| Simplified, Open summit | cooperative | 100 % | 0 % | 0 % | 86 % |
| Simplified, Great Famine | cooperative | 32 % | 68 % | 0 % | 74 % |
| Simplified, Great Famine | devoted (the rich rescue the starving in the last turn) | 100 % | 0 % | 0 % | 76 % |
| Simplified, Great Famine | selfish | 5 % | 15 % | 80 % | 29 % |
| Simplified, Armageddon | cooperative | 2 % | 12 % | 85 % | 49 % |
| Simplified, Armageddon | devoted | 75 % | 18 % | 8 % | 62 % |
| Full, Open summit | cooperative, good quiz (80 %) | 78 % | 20 % | 2 % | 64 % |
| Full, Great Famine | cooperative, good quiz | 8 % | 45 % | 48 % | 57 % |
| Full, Great Famine | cooperative, no quiz | 0 % | 0 % | 100 % | 58 % |
| Full, Great Famine | devoted, good quiz | 100 % | 0 % | 0 % | 63 % |
| Full, Armageddon | devoted, good quiz | 45 % | 42 % | 12 % | 56 % |

Selfish play still fails in the Simplified game: it removes rules, not the need to cooperate.

## 🎚️ Easy and hard nations

Every nation is rated Easy ★, Medium ★★ or Hard ★★★ with a short reason, one rating for each kind of game (`difficulty` and `difficulty_note`, `simple_difficulty` and `simple_difficulty_note` in `scenario_config.json`; the reasons never mention secret missions because the lobby is public). The rating is shown on the lobby cards, on the setup screen, in the Guide and on each nation's own phone, so the facilitator can give the hard nations to experienced participants and the easy ones to newcomers. `venv/bin/python tools/simulate.py --nations` plays many games and prints the share of its missions each nation meets in both kinds of game.

| | Full game | Simplified |
| :--- | :--- | :--- |
| Easy ★ | **Solaris** (rich and respected; the challenge is coordinating 4 delegates), **Aethelgard** (the strongest army and a calm people) | **Solaris**, **Aquila** (plenty of Silk, and its goals reward trading with everyone) |
| Medium ★★ | **Aquila** (its public mission needs every nation to trade) | **Sylvan** (everyone needs its grain), **Umbra** (one vote, but the Cores others want), **Aethelgard** (an army feeds nobody) |
| Hard ★★★ | **Umbra** (one delegate, one vote, the lowest Standing), **Sylvan** (everyone needs its grain, weak army), **Val-Khor** (starts with 30 Grain and competing goals) | **Val-Khor** (must buy food, and its public mission needs others to modernise) |

## 🧭 Running a session: saves, debrief and results

- **Clock console** (*Run the game* tab; the clock in the top panel opens it, and the panel itself has Pause and ±1 minute): one set of controls for whichever clock the phase has: the working session, the pause before a turn, the Grand Plenary debate, the Assembly vote, and, between turns and after the summit, a free countdown for a break or the debrief. Type minutes and seconds, nudge by ±10 s, ±1 min, ±5 min, pause, resume or reset to the default length.
- **Resources** (*Nations' numbers* tab): change several nations and several resources at once (add, take away or set to an exact number, typed), see exactly what each nation would end up with, and optionally tell the nations (news and a sound). Silent changes are written to the results report. In the table every value can also be typed (Enter, then confirm) or nudged with +/−.
- **Confirmations:** almost every action asks first, on the facilitator's deck and on the phones (decrees, offers, accepting a trade, motions, co-sponsoring, votes, taking a quiz question, attacking). A dialog ignores clicks and key presses for a third of a second after it opens, so the key or tap that opened it cannot also answer it.

- **Logins belong to one game:** a new game (server start, or "Start a new summit") logs every phone out; open phones go to the passcode screen by themselves and say why. If the old game is brought back they return to it by themselves. The facilitator login is kept.
- **No stale files:** pages and scripts are sent with `Cache-Control: no-cache` (the browser checks for a newer version every time) and game state with `no-store`.
- **Reflection debrief:** after concluding the summit, press **Start reflection** on the admin page. The projector shows the 12 reflection questions one at a time (`reflection_questions` in `scenario_config.json`), several with results from the game beside them. **Next question** and **Previous** step through them.
- **Results report:** admin → **Results report** (or **Download results** after the summit) opens a printable page with the outcome, final stats, missions, every trade, every motion and vote, and the full timeline. You can print it, save it as a PDF, or download it as HTML or JSON.
- **Screens stay awake:** the projector, phones and admin page ask the browser not to dim. This works on the hosted (https) site; on a plain-http LAN, browsers don't allow it.

## 💾 Saves: what happens when the server stops

The chip at the top of the deck says when the game was last saved ("✓ Saved 2 min ago"), and warns if an autosave fails.

**What is saved**

- **On the server** every 5 minutes while a game is being played and has changed (`AUTOSAVE_SECONDS`), at the start of every turn and at the end of the summit. A game nobody has started is not saved, and neither is a game where nothing has moved, so an idle screen cannot fill the list.
- **Safety copies** before a restart, a restore, a new summit and a reset. These and manual saves have their own place in the list (20), so the automatic saves (24, two hours of play) can never push them out.
- **In the facilitator's browser** every minute and at every step of the game, for a hosted server whose database is wiped when it restarts: five copies of this game, and the newest copy of up to two earlier ones. A new game cannot push out the last copy of the old one until it has itself been started. If the browser runs out of room it drops the oldest copies, and says so if not even the newest fits.
- **Save now**, **Download a save file** and **Load a save file** are on the Saves tab.

**When the server stops** (a crash, a dead battery, a restart). Every server start is a fresh game straight from `scenario_config.json`, so config changes always take effect (`FRESH_START=0` turns that off; under gunicorn it runs once from `gunicorn.conf.py`, never when a worker restarts). The game that was under way is not lost, because everything is on disk at all times:

1. The start makes a "Before server restart" save of it. If nothing had started but settings, nations or passcodes had been changed, it keeps those.
2. The deck (and the setup screen) offers it back for 24 hours, until a new game starts: **Bring it back** or **Start fresh**. It stays on the Saves tab either way. If the hosted server has lost it, the offer comes from the copy in the browser.
3. After bringing it back the **clock is paused** at the time it had left, so nothing runs out while the room gets back on its feet. A quiz question that was open becomes the nation's next question again, without a penalty. Phones that were in the game log back in by themselves. Press **Resume** when everyone is back.

Restoring any older save works the same way, and keeps a copy of the current game first. Screens that lose the server say so instead of freezing, and recover by themselves.

## 🧪 Tests

```bash
venv/bin/pip install -r requirements-dev.txt
venv/bin/python -m playwright install chromium   # once, for the browser tests
venv/bin/python -m pytest -q
```

- `test_summit.py`: engine and API tests. They run on a throwaway database, never on the `summit.db` of a real game.
- `test_i18n.py`: the translator's rules, that the Czech catalogues cover the missions, scenarios and quiz, that the files sent to browsers hold no secrets, and how the game and a device choose their language.
- `test_e2e.py`: click-through tests. They start the real server with logins enforced and drive a headless browser as phones, the facilitator and the projector, covering joining, trading, motions and voting, private motions and game-master questions, the quiz, the wiki, roster changes, the debrief, the report, the setup screen and every screen on a phone. For saves they really kill the server in the middle of a game (and wipe its database, like a hosted restart), start it again and check that the game and the phones come back. They are skipped if Playwright isn't installed.
- `tools/simulate.py`: plays hundreds of complete summits through the real engine with computer-controlled delegations (cooperative or selfish, different quiz skill, scenario and complexity) and prints how often the continent ends stable and how often each mission is met. Use it to check balance after changing numbers in `scenario_config.json`; `--simplified` compares the two difficulty settings.

## 🗂️ Front-end files

| File | Used by |
| :--- | :--- |
| `static/js/common.js` | every page (sounds, toasts, escaping, keep-screen-awake) |
| `static/js/realm.js` | phone console |
| `static/js/admin.js` | facilitator command deck |
| `templates/cards.html` | passcode cards to print (`/admin/cards`) |
| `static/js/projector.js` | projector screen |
| `static/js/map.js` | projector's animated map (Living Atlas) |
| `static/js/i18n.js` | every page when it is not in English: translates what scripts write (see [Languages](#-languages-english-and-czech)) |
| `static/style.css` | all pages; the header comment explains its sections |
