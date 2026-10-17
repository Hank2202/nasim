# Summit of Realms — Status & Review Notes

Last updated 2026-10-15. Run tests with `venv/bin/python -m pytest -q` (55 passing).

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

## Update 2026-10-15 (afternoon)
- **Theme:** light "illuminated manuscript" look everywhere. Parchment, ink, burnished gold, emerald, and serif headings from system fonts. Tokens are at the top of `static/style.css`; the "FANTASY THEME LAYER" sits at its end. The projector defaults to light; a dark mode stays available in Settings.
- **Wiki:** opening the Wiki tab enters a full-screen reading mode (`body.wiki-mode`). The game header and tab bar are hidden, and a × button returns to the previous tab.
- **Quiz:** still one attempt per question per nation. A nation's phones now refresh within a second when a teammate answers.
- **Motions:** players choose from a gallery of written-out templates, then edit title and terms. A target nation is used where needed (`target_realm_id`). Decided motions show the vote breakdown.
- **Bug fix:** motions that were already passed or rejected were being put back on the ballot at the next plenary.

## Update 2026-10-15 (evening): layout redesign and fewer nations
- **Phone console** (`realm.html`):
  - A nation banner (crest in the nation's colour, votes, turn and timer) replaces the generic header.
  - Realm tab: a "what's happening now" phase card with a timer bar, the treasury as 4 coins, vitals as bars, mandates as scrolls, decrees as tiles and the latest news.
  - World tab: nation cards with tier pips.
  - Trade tab: pick a partner from chips (playing nations only, updated live), resource pickers, steppers and a plain-English summary.
- **Projector:** `static/world3d.js` is replaced by `static/realm_map.js` (see the Living Atlas update below).
  - It draws an SVG parchment map, with regions placed by the Spireopedia geography.
  - Nations that aren't playing are drawn as hatched "Unclaimed lands" with no stats.
  - A "Council of Nations" side panel shows only playing nations, using tier pips (no exact numbers).
  - A session timeline and the motions on the ballot run along the bottom.
  - The Assembly vote screen has a for/against balance bar and a tile per playing nation.
- **Nation count:**
  - The admin page has an always-visible roster: tap a nation to add or remove it (at least 2 must stay).
  - Server-side rules:
    - Secret missions about an absent nation are skipped (`MISSION_REQUIRES` in `engine.py`).
    - Trades with absent nations are refused.
    - Logins and actions from absent nations are refused.
    - Co-sponsor requests can only go to playing nations.
- **Fixes:**
  - The projector debrief crashed (an undefined `verdictEl`).
  - Negative trade amounts let a nation take resources.
  - Trade notes and news were inserted unescaped, so players could inject HTML.
  - Raw LaTeX appeared on the admin page.
  - The lobby always said "Six nations".

## Update 2026-10-15 (night): Living Atlas + news ticker
- `static/realm_map.js` is now `LivingAtlas`, an animated map that fills the whole projector behind the panels.
  - **Terrain:** a heightmap built from blobs that follow the lore geography is painted once into a hill-shaded, parchment-grain texture with ink borders and coastline. It is repainted only when the roster changes, which takes about 0.13 s.
  - **Camera:** every frame the texture is drawn through a slowly orbiting, tilted camera that flies to each playing nation in turn, about every 11 s, with an overview in between. The flight also highlights that nation's card in the Council panel.
  - **On top of the terrain:**
    - upright mountains, forests, castles and temples;
    - the glowing Neutral Spire;
    - sailing ships, shimmering water and drifting clouds with shadows;
    - animated trade routes between nations that recently traded;
    - nation banners with crest and votes.
  - Absent nations are faded parchment labelled "unclaimed lands".
  - It ran at about 120 fps on the dev laptop and honours `prefers-reduced-motion`.
- A news ticker scrolls along the bottom of every projector screen; it rebuilds only when the news changes.
- **Map art pass:**
  - Sprites are painterly: gradient-shaded mountains with only an inked ridge line, trees in groves (broadleaf in the south, conifers in the north and west), and small stone castles flying Aethelgard's colour.
  - Every sprite has a soft contact shadow.
  - Nation labels are cartographer ribbons (small-caps lettering, folded tails in the nation's colour, a heraldic shield with the initial, a wax seal with the vote count) and scale with screen width.
  - Clouds drift slowly across a wide band and fade in and out, so they never pop.
- **Living map pass 2:**
  - **Rivers:** traced downhill from highland springs, painted into the terrain, with glints flowing downstream.
  - **Scheduled events**, cycling every 9–19 s, at most two at a time, each fading in and out:
    - a dragon flying over with its ground shadow and an occasional fire puff;
    - a sea serpent surfacing;
    - a whale spouting and diving;
    - a naval battle between ships in two playing nations' colours, with cannon fire and one ship sinking.
  - **Birds:** flocks drift across permanently.
  - **Seam fix:** the light square near Aquila was a shallow-sea shelf that ran to the texture edge. The shelf is now limited to the archipelago and the world texture is larger (1200×900).
  - **Projector theme:** dark mode is removed from the projector; an old saved "dark" setting hid the top-bar text.
  - **Parchment styling:** the Council sidebar and the news ticker are now parchment, and the sidebar compacts on screens shorter than 820 px.
- **Map pass 3:**
  - **River glints:** about 4× slower and subtler.
  - **Dragon:** wings now beat between raised and level, never swinging through the body, which had looked like helicopter blades. Dragons heading left are mirrored instead of flying upside down, and their tilt is limited.
  - **Clouds:** the "beak" artifact (a stray line joining the puffs) is fixed with separate sub-paths.
  - **Weather (rare), once per ten-event cycle each:**
    - a storm: a drifting thunderhead with its shadow, slanted rain and lightning bolts that briefly brighten the whole map;
    - a tornado: a swaying, spinning funnel wandering over land with a dust ring and debris.
- **Map pass 4:**
  - **Weather movement:** storms sweep right across the continent (about 23 units/s for 46 s); tornadoes move faster.
  - **Event order:** the first cycle now shows dragon, whale and tornado early; the storm is the 6th event.
  - **Settlements and roads:** 17 settlements with lore names (capitals match the Spireopedia), drawn as clusters of houses with roofs in the nation's colour and a keep for capitals.
    - 20 roads are routed with A* over a cost grid (lowland cheap, uphill dearer, water impossible, reuse of existing roads cheaper).
    - Roads are smoothed (Chaikin), painted as tracks with a dashed centre line, with dotted sea lanes for Aquila.
    - One cart travels each road.
  - **Map controls:** wheel or +/− to zoom, drag to pan, 0 or ⌂ for the whole continent, click a ribbon to select a nation. Interaction pauses the tour and orbit for 45 s, shown by an "Exploring the map · Resume tour" pill.
  - **Projector sidebar:** "Realm in Focus" shows one nation in large type (crest, region, capital, votes, public mandate, 7 tier meters, flags) with a row of crests to switch nations. It follows the map tour.
  - **Facilitator events:** Settings has "Summon on the map" buttons, and keys D/S/T/B/N/W trigger dragon/storm/tornado/battle/serpent/whale.

## Update 2026-10-17: autosave
- **Server autosaves:** the server snapshots `game_state` into a new `autosaves` table every 5 minutes, keeping the last 12. The check runs on each `/api/state` poll, so no thread is needed. A "Before restore" save is made before any restore.
- **Browser copies:** the admin page also keeps the last 6 saves in the facilitator's browser (`localStorage`), because Render's `/tmp` database is wiped when the server restarts.
- **Admin "Saves" tab:** Save now, Download save file, Load save file, and Restore from either list.
- **API:** `GET /api/admin/saves`, `GET /api/admin/save/export[?id=]`, `POST /api/admin/save/now`, `POST /api/admin/save/restore {id | snapshot}`. All are admin-only.

## Update 2026-10-17: tooling, debrief and results
- **Code split:** `static/app.js` became `static/js/{common,realm,admin,projector}.js`, and `realm_map.js` moved to `static/js/map.js`. Each page loads only its own script; `base.html` has a `page_scripts` block. The unused `RESOURCE_FRIENDLY` constant was removed.
- **CSS:** 132 dead selectors removed (old 3D projector, earlier console and council styles); the file went from 2,265 to about 1,780 lines, and its header documents the sections. The cleanup script only removed selectors whose classes or ids appear in no template or script.
- **Wake lock:** `keepScreenAwake()` in `common.js` is used on the projector, phones and admin page. It needs https or localhost.
- **Reflection debrief:**
  - The 12 questions from the Czech notes are in `scenario_config.json` (`reflection_questions`), each with an optional `context` (`verdict`, `missions`, `power`, `sizes`, `winners`).
  - `meta.reflection_step` is set by `POST /api/admin/reflection {step|null}`, allowed only after the summit concludes.
  - The projector stage is `#proj-reflection-stage`.
- **Results report:** `GET /admin/report` (HTML, add `?download=1` to download) and `?format=json`, admin only. The full news history lives in `news_archive` (up to 1,500 entries) and isn't sent to phones.
- **Phone fix:** the empty "Assembly is in session" box no longer shows after the summit ends.
- **Browser tests:** `test_e2e.py` (Playwright; dev dependencies in `requirements-dev.txt`, so not installed on Render). The tests in the file share one server and run in order, so later ones expect the motion created in `test_full_round`.
- **Test count:** 65 tests pass (60 unit/API + 5 end-to-end).
