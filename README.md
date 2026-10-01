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
