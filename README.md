# The Summit of Realms - Live Geopolitical Strategy Simulation Platform

A lightweight, real-time web application built for live educational simulations. It runs locally on a facilitator's laptop (`0.0.0.0:5000`) and serves real-time responsive interfaces to students' smartphones and room projectors over a local Wi-Fi network with **zero external internet required**.

---

## 🌟 Key Features

- **100% Self-Contained & Offline-First**: Zero reliance on external CDNs or web fonts. Pure flat UI design (no gradients), crisp typography, embedded SVG vector emblems, and synthesized Web Audio bells.
- **Dedicated Projector Screen (`/projector`)**: Designed for classroom/auditorium projectors. Features:
  - Big Turn indicator and giant countdown timer.
  - Continental Delegations Board showing public standing, vitality, stability, votes, and conditions (never reveals secret agendas!).
  - Live breaking news ticker and room Wi-Fi QR code.
  - Dynamic Plenary Floor mode: when a Flash Assembly is active, it transforms into a full-screen roll-call visualizer with real-time weighted voting bars.
- **Comprehensive Game Overview & Guide (`/overview`)**:
  - Detailed simulation primer explaining the 6 sovereign nations, starting endowments, and geography.
  - Socioeconomic formulas and mathematical laws cheat sheet (starvation thresholds, technological efficiency, plutocratic drift, complacency paradox).
  - Parliamentary statutory resolution dockets, domestic governance levers, high-stakes lore quizzes, and room setup guide.
- **Mobile Participant Cockpit (`/realm/<id>`)**:
  - **Persistent Bottom Navigation Bar**: Seamless switching between **Overview & Directive**, **News & Dispatches**, **P2P Trade**, **Motions & Assembly**, and **Continental Registry**.
  - Secret Uncomfortable Domestic Directive (classified expandable drawer).
  - Live resource telemetry (Grain, Cores, Silk) and state metrics bars (Vitality, Standing, Stability).
  - Real-time P2P Trading Hub with atomic transfers and pending trade notification badges.
  - Player-driven emergency motions with a **Second Motion** trigger.
  - 60-Second Flash Assembly Modal Overlay with animated countdown and live roll-call.
- **Automated Event Deck & External Library (`events.json`)**:
  - Pre-loaded catalog of 20+ narrative geopolitical dilemmas across all turns.
  - Facilitator can click **⚡ Trigger Next Recommended Crisis** to automatically select and inject an appropriate crisis, or pick from the catalog dropdown.
  - Option to enable **Auto-inject crisis on Turn advance**.
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
| Delegation | Ethos & Geography | Starting Endowments | Strategic Agenda |
| :--- | :--- | :--- | :--- |
| **Sylvan Concordat** | Bio-harmony, Greatweald Basin | Grain: 70, Cores: 35, Silk: 40, Mil: 30 (2 Votes) | **Granary Bastion**: Keep Grain $\ge 75$ despite famine pressure. |
| **Iron Val-Khor** | Heavy metallurgy, Mount Khor Spine | Grain: 30, Cores: 60, Silk: 25, Mil: 65 (2 Votes) | **Tech Hegemony**: Rush Cores to $75+$ to unlock Tech Efficiency. |
| **Solaris Ascendancy** | Sun marble terraces, High diplomacy | Grain: 50, Cores: 45, Silk: 65, Mil: 50 (**3 Votes**) | **Diplomatic Supremacy**: Maintain Standing $\ge 80$. |
| **Umbral Enclave** | Energy synthesis, Abyssal Rift | Grain: 40, Cores: 70, Silk: 30, Mil: 45 (2 Votes) | **Balance of Power**: Prevent any rival from holding $\ge 3$ votes. |
| **Aquila Maritime League** | Luxury silk guilds, Sea of Glass | Grain: 45, Cores: 40, Silk: 80, Mil: 55 (2 Votes) | **Plutocratic Monopoly**: Finish as the reigning richest nation. |
| **Aethelgard Dominion** | Feudal chivalry, Northern Steppes | Grain: 60, Cores: 50, Silk: 35, Mil: 75 (2 Votes) | **Iron Shield**: Maintain Military $\ge 80$ and Stability $\ge 70$. |

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
1. **Working & Bilateral Trade Session (5:00 Min)**:
   - Roam the room freely for face-to-face bilateral diplomacy.
   - Execute instant atomic P2P trades (Grain, Cores, Silk, Military Power).
   - Enact internal state decrees (relief, forges, galas, security, mustering).
   - Read lore dossiers and answer high-stakes quizzes (+15 resource on success, -5 standing on failure).
   - Author statutory resolutions for the Plenary docket.
2. **Plenary Floor Debate & Flash Assembly (3:00–5:00 Min)**:
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
   - Use the **Automated Event Deck** to trigger crises or set **Auto-inject crisis on Turn advance**.
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
