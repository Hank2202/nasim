# Summit of Realms — Status & Review Notes

Last updated 2026-10-18. Run tests with `venv/bin/python -m pytest -q` (102 passing: 93 unit/API + 9 end-to-end).

## Decisions from the user
- Host on the easiest free option: **Render** (`render.yaml`). Players join by scanning a QR code.
- GitHub repo is **private**. **English only.**
- Quiz: **same questions for every nation**, **one attempt per question**, wrong answer = **lose the same resource and amount the question would have paid** + permanent lock (changed 2026-10-17; it used to be −5 Standing).
- Motions: co-sponsors are anonymous; a motion offered to one nation is seen only by that nation. "Question to the Game Masters" is a template that, like any motion, needs a co-sponsor and a passing vote; then the facilitators answer it publicly. Each nation may table 2 motions per turn (setting `motions_per_turn`).
- Crises: no automatic big catastrophes in the famine scenario; the storyline already carries the big crisis. Small random events are a random amount between 0 and the set maximum (float, default 5), many kinds, good and bad, default 6 per turn. The **Armageddon** scenario adds large disasters at random (3 per turn) and more/larger small events.
- Clocks: when time runs out an alert sounds and the game moves to the next phase by itself.
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

## Update 2026-10-17: map resolution and quality modes
- **Presets:** the `QUALITY` table in `static/js/map.js` has three presets:
  - **High:** texture 2.25 px per world unit (2700×2025), heightmap every 1.5 units, up to 2× device pixels, all effects.
  - **Balanced:** 1.5 px per unit (1800×1350), heightmap every 2 units, up to 1.5× device pixels.
  - **Low:** 1 px per unit, heightmap every 4 units, 1× device pixels, 30 fps cap, and no sparkles, river glints, birds or cloud shadows.
- **Auto (default):** starts on Balanced, measures the frame rate for 5 s, then switches once: below 32 fps goes to Low, above 55 fps with 8 or more CPU cores goes to High.
- **Setting:** the choice is stored in `localStorage.map_quality` and set from projector Settings → Map quality.
- **Faster painting:** `paintTexture` samples each pixel's height once and reuses it for shading and coastline ink. A full rebuild takes about 0.5 s on Balanced and 0.9 s on High, and runs only at load, on a quality change or on a roster change.
- **Fine relief:** two extra fine-relief terms in `elevation()` add detail that shows on the sharper modes.
- **Test:** `test_map_quality_modes` in `test_e2e.py`.

## Update 2026-10-17: setup screen, auto-advance, small events, private motions
- **Settings:** per-game settings are stored in the db key `settings` and merged over `game_settings_defaults` (scenario_config.json) by `engine.settings()`, which also adds `max_turns`, `grain_consumption` and `positive_share` from the chosen difficulty. `update_settings()` clamps values (`SETTING_LIMITS`). `POST /api/admin/settings`, `POST /api/admin/setup/new` (`start_new_summit`: autosave → reset → keep roster/delegates/PINs), `POST /api/admin/pins/shuffle`.
- **Setup page:** `templates/setup.html` at `/admin/setup` (scenario, difficulty, nations/delegates/passcodes, clocks, small events).
- **Scenarios:** `famine` keeps the Round 2 military rule and Round 3 famine + Food Acts; `open` has none of them. Difficulty: gentle/standard/harsh = 15/20/25 grain per turn.
- **Clock (`_tick`, run on every `/api/state` poll):** working timer expiry → "Time is up!" alert → `_advance_after_working()` (plenary if motions qualified, else straight to the next turn). Quick-plenary vote timer (`vote_timer_end`) → settle → `_advance_turn_or_finish()`; Grand Plenary debate → vote → next motion → … → turn summary → results. Between turns `intermission_end` gives a short pause before the next working timer starts. `meta.display_timer` tells every screen which countdown to show. With `auto_advance` off, only the alert fires.
- **Small events:** `minor_events` in scenario_config.json (6 good, 7 bad). `_check_minor_events` schedules `minor_events_per_turn` random moments per working session; `fire_minor_event` picks one nation and moves resources by at most `minor_event_max`. The old per-minute catastrophe rolls (`_check_minute_catastrophes`, `_check_automated_event_triggers`, auto-crisis toggle) are gone; catalog crises are manual only. Admin has "Good news now" / "Bad news now".
- **Grain at the end:** the last turn now eats like the others (`_consume_grain`, applied once in `conclude_summit`), so the results reflect the final meal.
- **Motion privacy (`app._private_view`):** phones get `support_count` instead of the co-sponsor list; targeted drafts are hidden from third parties; `gm_question` entries are visible only to the asking nation (and the admin). `answer_question()` + `POST /api/admin/question/answer {id, answer, public}`.
- **Bugs fixed:**
  - `draft_proposal` overwrote the cordon target with the co-sponsor restriction (variable reuse), so a cordon could hit the wrong nation.
  - A new game kept `trade_partners`, `military_trades` and `news_archive` from the previous game (Aquila's missions counted old trades).
  - The grain tax, embargo and continental cordon also applied to nations not playing.
- **Simulator:** `tools/simulate.py` plays full summits through the engine (40 games per row, 6 nations, famine scenario, standard settings unless noted):

  | Delegations | Stable | Fragile | Crisis | Missions met | Best game |
  | :--- | ---: | ---: | ---: | ---: | ---: |
  | Cooperative, quiz 80 % right | 100 % | 0 % | 0 % | 76 % | 18/21 |
  | Cooperative, quiz 40 % right | 100 % | 0 % | 0 % | 66 % | 15/21 |
  | Cooperative, no quiz | 70 % | 2 % | 28 % | 55 % | 13/21 |
  | Selfish, random quiz | 0 % | 5 % | 95 % | 28 % | 8/21 |
  | Cooperative, quiz 80 %, gentle | 100 % | 0 % | 0 % | 78 % | 17/21 |
  | Cooperative, quiz 80 %, harsh | 100 % | 0 % | 0 % | 71 % | 17/21 |

  Findings (not acted on; balance changes need the user's decision):
  - The game is winnable: cooperation is what matters; selfish play almost always ends in Continental Crisis.
  - Grain arithmetic: 330 at the start vs 450 needed (3 × 20 × 6 eaten + 90 famine). Food Act B adds 90; the rest must come from the quiz (up to 50 grain per nation), tech efficiency and the grain tax. So the quiz is the main food source, and difficulty barely matters once a group answers well.
  - `aethelgard_superiority` and `valkhor_contain_military` cannot both succeed (if Aethelgard leads the second-strongest by 20, it leads Val-Khor by at least 20). Max possible with all six nations and full delegations is 20/21; this looks like intended tension.
  - Hard but possible (tension missions): `sylvan_winter` (≥70 grain vs feeding everyone), `aquila_wealth` (+25 over everyone while trading away), `valkhor_tech` (+20 cores vs four nations at 60), Umbra's ≤90 military vs Aethelgard's superiority.

## Update 2026-10-17 (later): event variety and Armageddon
- **Settings:** `minor_events_per_turn` 0–30 (default 6), `minor_event_max` is a float 1–50 (`FLOAT_SETTING_LIMITS`), new `large_events_per_turn` 0–10 (default 0).
- **Small events:** each effect moves `max(1, round(uniform(0, max × |weight|)))`. `minor_events` grew from 13 to 50 (26 good, 24 bad), several with two effects.
- **Scenarios:** each scenario in `scenarios` has `famine_storyline` (replaces the hard-coded `scenario == "famine"` checks, including the Round 2 grain transit loss, which used to apply in every scenario) and `suggested` event numbers that the setup page fills in. New `armageddon`: famine storyline + 10 small events (max 8) + 3 large disasters per turn.
- **Simulation with the new defaults** (40 games per row): famine-scenario rows are unchanged within noise. Armageddon, cooperative: good quiz 98 % stable / 2 % fragile, 69 % of missions; weak quiz 70 % stable / 30 % fragile, 61 % of missions. Harder, still winnable.
- **Large disasters:** `fire_large_event()` picks a catastrophe whose terrain matches an active nation and calls `trigger_catastrophe` (which now targets only active nations; `_apply_catastrophe` also handles `military`). Four new catastrophes: dragon raid, great storm, tornado swarm, meteor shower. `_check_scheduled_events` (was `_check_minor_events`) plans both kinds per working session; changing the counts mid-session replans the remainder. Admin: **Random disaster now** (`POST /api/admin/event/large`).
- **Finding the setup screen:** `app.game_in_progress()` (clock started, a trade or motion, or past Turn 1). Before that, `/api/auth/admin` returns `next: "/admin/setup"` and the login page goes there; the command deck shows a `.setup-banner` link (highlighted while no game has started), because the header links are hidden on narrow screens. Admin cookies last 24 h, so a browser that logged in earlier is not asked again.

## Update 2026-10-17 (evening): questions are voted, motion limit, editable templates
- `gm_question` lost `no_vote`: it is drafted, co-sponsored and voted like any motion (`_apply_proposal_effect` just returns a note). `answer_question(id, answer)` works only on passed questions and always publishes a "THE GAME MASTERS ANSWER" news item; the answer is stored on the proposal and shown on the decided motion card. `conclude_summit` leaves questions out of the passed/failed lists, so they cannot be used to farm Solaris' "3 resolutions" mission. The private-question card on phones and the private/public choice on admin are gone.
- `draft_proposal` refuses a nation's motion once it has tabled `motions_per_turn` (default 2, 1–10, on the setup screen) in the current turn. Phones show "You can table N more" and disable the templates at 0.
- Phone motion form: hint box, "edit me" tags and dashed fields make clear the template wording is only an example; template buttons say "Start from this".

## Update 2026-10-18: review for fewer nations and gameplay gotchas
**Fewer nations**
- `scaled_targets(n)` in `engine.py` is the single place for mission targets written for six nations (Val-Khor's Cores, Solaris' broad support, Aquila's network and partners). Mission texts and the end-of-game check both use it. Changed at five nations: Solaris needs 3 nations per resolution (was 4 of 5), Aquila's network needs 3 of 4 (was all 4). Six-nation values are unchanged.
- Secret missions with `requires` in `scenario_config.json` switch to their `stand_in` when the nation they are about is absent: `sylvan_defense_home`, `valkhor_parity`, `solaris_contain_rivals`, `aethelgard_contain_rivals` (evaluated in `conclude_summit`). Before, these missions were dropped, leaving delegates without a mission (e.g. without Aethelgard, Sylvan had 1 mission for 2 delegates and Val-Khor 2 for 3).
- Phones re-render the public and secret missions when they change (`renderMissions` in `realm.js`); they used to be fixed at page load. The setup page shows each nation's number of secret missions and advises which nation to leave out.
- `tools/simulate.py --rosters` plays every 5-nation roster. With cooperative play all rosters ended stable in all games (30 per row, good and weak quiz). Missions met least often are the designed conflicts (`aethelgard_superiority` vs `valkhor_contain_military`) and tension missions.

**Bugs fixed**
- A nation whose Stability hit 0 at the end of a turn was forgotten: the flag was written to `meta` inside `_recalculate_all_realms`, and `process_end_of_turn` then saved its older copy of `meta` over it. The flag now lives on the realm (`stability_hit_zero`), which callers save with their changes.
- Food Act A destroyed the surplus above 50 Grain when no nation was below 20. Now nothing changes in that case.
- The admin's Round 1/2/3 buttons applied effects on top of the automatic ones: pressing "Round 3" in Turn 3 took another 15 Grain from everyone, and "Round 2" left the grain transit loss on in later turns. In scenarios with the famine storyline the buttons now only repeat the announcement; in the Open summit they apply Round 2 rules for the current turn (`meta.round2_rules_turn`) and the famine once (`meta.famine_applied`, shared `_apply_great_famine`).
- After the summit concluded, phones could still trade, answer the quiz and table motions (changing numbers after the results). Blocked (`_summit_over`). Motions and co-sponsoring are now only possible during the working session, since the Assembly docket is fixed once the vote starts.
- `create_trade` did not validate the requested resource (accepting such an offer crashed); accepting an offer from a nation that has left is refused.
- Trade offers and their private notes were broadcast to everyone in the news, with amounts. Now offers are private and the news only says which two nations traded (the doc: nations learn about each other from people, not the screen).
- Hard-coded texts: "5-minute debate", "-20 Grain awaits", "20-minute working session" now follow the settings.
- The Guide, README and phones described rules the engine never had: the "Complacency Paradox" output slump (phones even showed a warning), a −5 Stability per turn for the wealthiest nation, and a cordon that "blocks foreign trade". Texts now describe what the engine does (cordon: +10 Stability and less damage from plague, border surge and tsunami).
- Ranking: `score` is now the percentage of the nation's missions met (ties: public mission, then count). It used to be 100 points per mission plus all stats, which ranked big delegations (more secret missions) and rich nations higher by construction.

**Open design questions for the user** (not changed)
- The doc's reflection questions speak of each delegate's *personal* secret mission; phones show all of a nation's secret missions to every delegate.
- The +1 vote for the wealthiest nation is not in the doc: Aquila (Grain + Cores + Silk = 170) starts with 3 votes instead of the doc's 2.
- Vitality counts for nothing at the end, so the Relief decree (−15 Grain → +15 Vitality) is a trap during a famine.
- Technological Efficiency (Val-Khor eats 15 instead of 20 from the start) is not in the doc.

## Update 2026-10-18: fresh game on every server start
- `engine.fresh_start()` (autosave "Before server restart" if a game was under way → clear `settings` → `reset_simulation`) runs at every server start: from `app.py`'s `__main__` (run.sh) and from `gunicorn.conf.py`'s `on_starting` hook (master process, once per start; gunicorn loads that file automatically). `FRESH_START=0` turns it off.
- `meta.game_id` is new for every game. Nation login cookies are signed as `realm:<id>:<game_id>`, so any new game (restart, Reset, new summit) logs phones out; `realm.js` reloads when it sees a different `game_id`, and the realm page clears the lobby's `has_auth_*` marker when it bounces a stale login. `reset_simulation` also frees all seats. The admin cookie is unchanged.
- `after_request`: `Cache-Control: no-cache` for pages and `/static/`, `no-store` for `/api/`.
- `game_in_progress()` moved into the engine.

