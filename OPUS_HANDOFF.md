# Summit of Realms — Status & Review Notes

Last updated 2026-10-15. Run tests with `venv/bin/python -m pytest -q` (51 passing).

## Decisions from the user
- Host on the easiest free option: **Render** (`render.yaml`). Players join by scanning a QR code.
- GitHub repo is **private**. **English only.**
- Quiz: **same questions for every nation**, **one attempt per question**, wrong answer = **−5 Standing + permanent lock** (unchanged penalty).
- `MGV 2026 školení s Johanem.md` (Czech facilitator notes) is the reference for starting values and missions. `scenario_config.json` matches it.

## What exists now

### Hosting & security (app.py, models.py, engine.py)
- Login cookies are signed and HttpOnly, using `SECRET_KEY`. Every `/api/admin/*` POST needs the facilitator login. Every player write must come from that realm's own login.
- The `?auth=1` shortcut works only in tests or when `ALLOW_AUTH_PARAM=1` is set.
- Failed logins are throttled.
- `sanitize_state()` hides from non-admin viewers:
  - all PINs;
  - other nations' secret missions;
  - other nations' exact stocks (they see tiers only);
  - quiz progress.
- A global request lock serialises state-changing requests, because the engine does read-modify-write on SQLite and the server is threaded.
- SQLite runs in WAL mode with a busy timeout.
- Deployment: `/healthz`, `render.yaml`, `Procfile` (gunicorn, **1 worker**).
- Environment variables: `SECRET_KEY`, `ADMIN_PASSCODE`, `SUMMIT_DB_PATH`, `PUBLIC_URL`.
- QR codes encode the public URL when the app is hosted.

### Spireopedia (wiki.py, lore_articles.json; rendered in the phone's Wiki tab)
- 22 Wikipedia-style articles: 6 nations, plus history, geography, resources and institutions.
- In-world calendar: AC (After Convergence); the present is 304 AC.
- It is **part of the game, not a separate site**. It is read only in the phone console's Wiki tab.
- The tab fetches JSON from `/api/wiki`, `/api/wiki/<slug>` and `/api/wiki/search`. These need a delegation or facilitator login.
- Article text is escaped and rendered to HTML on the server. Links between articles, Back and search all stay inside the tab.
- Map capitals in `static/world3d.js` match the articles: Rootholm, Khorgate, Helion, Lanternfall, Halcyon Quay, Aethelhold.

### Quiz (lore_quiz.json, engine.get_quiz_for_realm / submit_lore_quiz)
- 32 questions, shared by every nation, unlocked by turn (10 / 11 / 11).
- Correct answer: +5 Grain, Cores or Silk. Maximum total from the quiz is 160, close to the old 8 × 15 = 120.
- Each question names the article that holds its answer.
- `GET /api/quiz/<realm>` needs that realm's login and never includes answers for unanswered questions.
- `POST /api/lore/quiz` checks the answer on the server and stores the chosen option (`quiz_answers`), so every phone in the delegation shows the result.
- The old `lore_encyclopedia` dossiers were removed from the config and from the state API.

### UI consistency
- `static/style.css` ends with a **shared component layer**:
  - layout: `page-head`, `section-sub`, `inset`, `callout`, `stack`, `row`;
  - controls: `chip`, `segmented`, `status-pill`, `action-row`;
  - quiz and registry styles;
  - semantic colour tokens (`--ok`, `--warn`, `--danger`), focus rings, and toast variants.
- One header in `base.html` with blocks `nav_links`, `status_pills` and `header_extra`. On phones it collapses and no longer overflows.
- Phone console (`realm.html`) has six tabs: Realm / World / Trade / Motions / **Wiki** / **Quiz**.
  - Reading (Wiki) and answering (Quiz) are separate tabs.
  - Inline styles were mostly replaced with classes.
  - The registry under World renders live.
  - The quiz uses select-then-confirm ("Lock in B"), because a wrong answer is permanent.
- Lobby, admin header, admin login and guide were restyled with the same components. Decorative emoji were removed from buttons (realm emblems kept).
- The guide's text was updated for the new tabs, the quiz and hosting.
- Projector:
  - the top bar no longer wraps;
  - a **Join QR** button sits in the top bar;
  - ethos text in the map panel wraps instead of overlapping.
- Admin delegations table shows each nation's quiz score.

## Not verified / open
- **Not deployed to Render yet**; current free-tier terms are not re-checked. Free instances sleep when idle, and the DB in `/tmp` resets on restart.
- Admin, projector and overview still contain many inline styles. They look consistent now, but a deeper conversion to the component classes is possible.
- The plenary voting overlay on phones and the end-of-summit debrief were not visually re-checked after the CSS changes. They use the same classes as before.
- `load_scenario_config()` re-reads the JSON on every call (fine at this scale; cache it if load matters).
