# Summit of Realms — Status & Review Notes

Last updated 2026-11-07. Run tests with `venv/bin/python -m pytest -q` (see the Tests line at the bottom for the current count).

## Decisions from the user
- Host on the easiest free option: **Render** (`render.yaml`). Players join by scanning a QR code.
- GitHub repo is **private**. **English and Czech** (Czech added 2026-11-07; English stays the default and the source of every text).
- Quiz: **same questions for every nation**, **one attempt per question**, wrong answer = **lose the same resource and amount the question would have paid** + permanent lock (changed 2026-10-17; it used to be −5 Standing).
- Motions: co-sponsors are anonymous; a motion offered to one nation is seen only by that nation. "Question to the Game Masters" is a template that, like any motion, needs a co-sponsor and a passing vote; then the facilitators answer it publicly.
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
    - One cart travels each road. (Replaced 2026-11-07: caravans and ships follow real trades; see the last update.)
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
- (Removed later: there is no motions-per-turn limit any more.)
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

## Update 2026-10-19: structured motions, timed quiz, war, clock console, bulk resources, confirmations, nation difficulty
**Motions (`motions.py`)**
- A motion carries `effects` (structured lines: `transfer`, `levy`, `boost`, `redistribute`, `flag`) and `effect_text` (sentences generated from them). `SummitEngine._motion_effects` builds both from a template's `builder` (`fixed`, `cordon`, `redistribute`, `levy`, `pact`, in `scenario_config.json`) and the player's `params`; `POST /api/proposal/preview` returns the sentences for the live preview. `_apply_proposal_effect` carries the lines out (`motions.apply_lines`) and stores `result_text`; the quick plenary now posts one news item per motion (before only a summary). Proposals without `effects` (old saves, the Food Acts, direct calls in tests) still use the old hard-coded branches.
- Player-made value is limited: only fixed templates `boost`; transfers are value-conserving (pool shared by receivers, remainder to the first ones); there is no cap per amount (only a 999 sanity limit, `MAX_AMOUNT`): a transfer or levy takes `min(amount, what the nation has)` and receivers get only what was taken. At most 3 pact lines. No motions-per-turn limit any more (the `motions_per_turn` setting is gone). Template `open` (builder `open`) has no effect lines: when passed the proposal gets `awaiting_gm`; `complete_open_motion` / `POST /api/admin/motion/complete` marks it done (admin inbox in the Resolutions tab). Selectors: nation ids, `@me`, `@target`, `@all`, `@others`, and (resolved when the motion passes) `@richest/@poorest/@strongest/@weakest`.
- **Balance change:** the old grain "tax" created grain (+15 for every poor nation, −10 for every rich one); it is now the value-conserving `redistribute`. Together with the harder quiz this removed the easy food and made Standard much harder (see simulation below).
- New template `pact` (Resource Pact); `tax` is "Resource Redistribution", `embargo` is "Sanction or Embargo". The admin sees "If passed (automatic)" and "Carried out" on every motion card.

**Quiz**
- One question at a time: `quiz_start` (the player presses Start; no extra dialog), the server holds `realm.quiz_active` {question_id, deadline, shuffled order}, `submit_lore_quiz` only answers the open question, `_expire_quiz_questions` (every poll) settles a late question as wrong, `_resolve_quiz` applies the symmetric stake. `quiz_seconds` setting (5–60, default 15). Order and stake are random per nation: `_quiz_next` draws a random unanswered, unlocked question and a random stake (`quiz.stake_min`..`stake_max`, default 1..9, mean 5) and keeps it in `realm.quiz_next` until it is started, so a refresh shows the same one; the stake of the open question is `realm.quiz_active.stake` and is logged in `quiz_log`. `reward_amount` in `lore_quiz.json` is ignored. `GET /api/quiz/<realm>` returns progress/open question/next stake/history; `POST /api/quiz/start`. The open question never contains the answer or the article.
- The bank has 62 questions (`tier` standard 5 / hard 8). The hard ones ask for details from `lore_articles.json`.
- News: no per-answer items; `meta.quiz_digest` counters and `_post_quiz_digest` (every 5 minutes after the first answer, and at the end of a turn and of the summit). Names and resources are left out.
- Declining a question postpones it (the next question for a nation is always the first one it has not answered): a nation cannot skip past a hard question, only stop.

**War (`battle.py`)**
- See the README section. Engine: `get_war_status`, `battle_preview` (scouts: blurred, seeded per game/turn/pair so asking again changes nothing), `declare_attack`, `_attack_blocker` (enabled, working phase, `attacks_from_turn`, `attacks_per_turn`, ≤2 attacks received per turn, min Military, supplies). Turn weather is `meta.weather`, rolled at reset and in `process_end_of_turn`. Battles are in db key `battles` (40 kept, `state.battles` has the last 12); `private` holds both sides' numbers: admin sees both, each nation only `private.mine` (`app._battle_view`).
- Phone: War room card, scouting report, confirmation, battle modal (`static/js/battle.js` `BattleScene`); projector: the battle takes over the Realm in Focus panel (`#battle-stage`, class `battling` on `.atlas-side`; queue in `projApp.nextBattle`) and `map.addWar` (burning arc between the capitals); sounds: cue type `battle` (`synth.playBattle`).
- Tuning in `scenario_config.json` → `battle`; defaults in `battle.DEFAULTS`. Luck ±12 %, readiness 0.35–1.9 (weights stability .22, grain .20, cores .14, vitality .10, standing .06, silk .04, curve 1.6).
- **Fog of war / intel (`battle.intel`, `reveal`, `modifier_lines`, `scouting`):** luck, power totals and the facilitators' `war_power_pct` / `war_defence_pct` are never sent to players (`meta.weather` is reduced to id/name/text by `sanitize_state`; `battle.private` (exact, admin) vs `battle.report` (what each nation is told) and `_battle_view` only passes `report[side]` as `private.mine`). Reach = round(wealth / 28) modifiers (max 9), biggest first; accuracy = (Silk+Cores)/2/80 capped at 0.9, own side +0.3; displayed as a word (<0.3), a range (<0.6) or `about ±N%`; noise is seeded so repeats are identical.
- **Animation:** `BattleScene` in `static/js/battle.js` draws two armies (4×5 soldiers each, banners, fall times seeded from the battle id, loser flees after the rout phase) on a canvas whose backdrop depends on `terrain.id` and `weather.id`; timeline march 1.7 s, melee to 5.6 s, rout, result at 7.4 s (projector pop-up lasts 11 s).

- **Attack modes:** `declare_attack(attacker, defender, mode)`: `siege` (default of the API) writes a record to db key `sieges` (public view `public_sieges()` in `state.sieges` with `eta`) and is fought by `resolve_sieges()` when the working clock (`meta.turn_timer_remaining`) reaches `arrive_remaining = remaining − 120`; `_tick` calls it, `process_end_of_turn` and `conclude_summit` force it. `surprise` (default of the engine function) is fought at once through `_fight` with `battle.modes.surprise` (double supplies, `attacker_bonus` 0.08, extra `attacker_penalty` Standing −15 / Stability −8, `defender_win_standing` +5). Sieges count towards `attacks_per_turn` and `max_attacks_received_per_turn`. `admin_siege(id, 'arrive'|'cancel')`, `POST /api/admin/siege`. `battle_preview` returns `modes.siege` / `modes.surprise` (label, cost, summary, can_attack). A battle record has `mode`.

**Facilitator tools**
- Clock console: `engine.admin_clock(action, value)` / `POST /api/admin/clock` act on the clock of the current phase (`clock_info`: working, intermission, debate, vote, or a free countdown `meta.free_timer_*` between turns and after the summit). Pausing the vote clock is new. Pause now rounds instead of truncating (a pause used to lose up to a second).
- Bulk resources: `admin_bulk_adjust` / `POST /api/admin/resources/bulk` (add/take/set, several resources and nations, optional announcement); silent changes go to the report timeline as `admin` entries (`add_admin_log`). Typed cells in the telemetry table (the table is not rebuilt while someone types). `admin_override_realm` now clamps values.
- Confirmations: `confirmAction` in `common.js` (themed dialog, Escape cancels, answers are ignored for 350 ms so the key or tap that opened it cannot answer it; before this, pressing Enter in a typed cell confirmed instantly). Used for nearly every admin and phone action; the native `confirm()` calls are gone.
- **Modifiers:** `realm.modifiers` {votes, grain_use_pct, war_power_pct, war_defence_pct} plus the flags `is_quarantined`, `is_striking`, `tech_efficiency_unlocked` (`efficiency_switched_off` stops the automatic unlock at 75 Cores); `engine.modifier_sheet`, `admin_set_modifiers`, `GET/POST /api/admin/modifiers`; applied in `_recalculate_all_realms` (votes), `_consume_grain` and `battle.side_power`. `modifiers` is stripped from every non-admin state.
- **Action journal:** `app.journal_before/journal_after` snapshot the nations around every POST (except auth, journal, reset, roster and save-restore requests) and `engine.journal_record` stores the field deltas (`db key journal`, 200 kept, cleared by `reset_simulation`); `undo_journal` adds the opposite delta (flags and modifiers are set back), allowed only for the paths in `app._JOURNAL_REVERSIBLE`. UI: Resource Overrides tab.
- Settings added: `quiz_seconds`, `attacks_enabled`, `attacks_from_turn`, `attacks_per_turn` (setup page, "War" card).

**Nation difficulty:** `difficulty` (1 easy, 2 medium, 3 hard; three stars) and `difficulty_note` per realm (notes must not mention secret missions: the lobby is public); `templates/_difficulty.html` macros show them in the lobby, setup, Guide and on each phone. Ratings follow `tools/simulate.py --nations` (share of its missions each nation meets, 24 games, devoted delegations, quiz 80 % / 45 %, warlike): Solaris 93–99 %, Aethelgard 71–74 % (easy); Aquila 67–75 % (medium); Umbra 50–56 %, Sylvan 33–61 %, Val-Khor 7–9 % (hard).

**Simulation (`tools/simulate.py`, standard difficulty unless noted, 16–20 games per row)**
- `devoted` delegations (cooperative, and in the last turn the rich rescue the starving): Gentle ends "Stable" in 100 % of games even with no quiz income; Standard 100 % stable with a quiz at 80 % knowledge but about 19 % stable / 62 % fragile / 19 % crisis with a weak quiz; Harsh needs the strong quiz (44 % stable at 80 %, otherwise crisis).
- Plain `cooperative` (no last-minute rescue, keeps secret-mission reserves) fails without a very good quiz: the economy is tight, and the quiz used to be the main food source. A nation needs to know about 65 % of the hard questions to profit from them.
- `warlike` (attacks whenever the scouts say Favourable): about 3 battles a game; Stable endings fall from 100 % to 44 % (good quiz) and Crisis rises from 0 % to 31 %; with a weak quiz 94 % crisis. War is the "defection" option and it is costly for the continent by design; facilitators can switch it off or unlock it later.
- Open question for the user: is Standard too hard without strong quiz players? The levers are the `difficulties` in `scenario_config.json` (grain per turn), the quiz stakes (now random 1–9), or making Gentle the default. (The figures above were measured with the old fixed stakes of 5 and 8; the random-stake figures are listed under the Tests line.)

**Simulation with random quiz stakes (1–9, mean 5; 12 games per row for the sweep, 6 for `--war`):** `devoted` peaceful 100 % Stable with a quiz at 80 %, with a weak quiz (45 %) 0 / 67 / 33 % Stable / Fragile / Crisis; `warlike` with a good quiz 67 / 33 / 0 % (about 3 battles a game), with a weak quiz 83 % Crisis. Plain `cooperative` (no last-minute rescue): Gentle 92 % Stable, Standard with a good quiz 8 / 50 / 42 %, Harsh 92 % Crisis. Conclusion unchanged: Standard needs good cooperation and a decent quiz; the random stakes did not change the picture noticeably.

**Tests:** 192 (173 unit/API, 19 browser). Added in the last round: random quiz stakes/order, no motion limit, uncapped amounts bounded by holdings, the open motion, modifiers (sheet, limits, votes, grain use, war power, efficiency flag, privacy), the action journal (record, undo, later changes kept, non-reversible entries, reset), war intel (reach grows with wealth, accuracy grows with Silk and Cores, never exact, no luck or facilitator adjustments in reports), and browser tests for the new quiz start flow, reversing a mistaken change, editing modifiers and carrying out an open motion. The browser check of the army animation was done by eye (screenshots), not by an automated test.

## Update 2026-11-06: two difficulty settings, the Simplified game, code review
**Decisions from the user**
- Difficulty is **two settings**: the game's **complexity** and the **scenario**. The old third setting (`difficulties`: gentle/standard/harsh) is gone; what it set now belongs to the scenario and can be typed on the setup screen.
- The reduced-complexity game: motions cannot be edited (only the amount), and they are fully automated. No quiz, and the starting resources make up for it. Other reductions were left to the implementer. The Full game stays as it was.

**Engine**
- `rules()` gives the rules of the game being played: `{**FULL_RULES, **complexities[meta.complexity]}` with switches `quiz`, `war`, `free_motions`, `grand_plenary`, `one_secret_mission`, `hide_vitality`, `live_hints`, `hidden_decrees`, `starting_bonus`. A game keeps the complexity it was dealt with: `meta.complexity` is set in `reset_simulation`. Saves without it play the full game. The default is `full`.
- `settings()` returns `rules` too and forces `attacks_enabled` off when the game has no war; `settings(as_chosen=True)` gives what the setup screen chose, so the War card keeps its value for the next full game. `update_settings` applies a new complexity at once while `game_in_progress()` is false (`_switch_complexity` swaps the starting bonus, same `game_id`, and open phones reload by themselves because `realm.js`/`admin.js` compare `rules.id`); during a game it is stored for the next new summit and the message says so.
- Grain and good news: `grain_consumption` (5–60) and `good_news_percent` (0–100) are ordinary settings. `settings()` falls back to the scenario's `suggested` values, and `update_settings` drops typed values when the scenario changes without new ones. `positive_share` is derived.
- `motion_templates(rules)`: `resolution_types`, or `simple_motions` plus the Food Acts. `_fill_simple_motion` fills `{amount}` and `{me}` into `lines`, `effect_plain`, `title`, `terms`; `draft_proposal` ignores the client's title, terms and targets in the simplified game. The carrying out is the same `motions.apply_lines`.
- `start_plenary_session`: quick vote in the last turn too when `grand_plenary` is off. `_evaluate_missions`/`_mission_context` were moved out of `conclude_summit` (same checks) and also feed `mission_status` on each realm when `live_hints` is on (`_attach_mission_status`); `sanitize_state` only lets a nation see its own, and the hint never quotes another nation's numbers (`SELF_CONTAINED_MISSIONS`, `pub_hint`).
- `hide_vitality`: vitality effects are skipped in small events and disasters, so the news never mentions it. The number still exists on the realm (old code paths, facilitator table) and only the starvation penalty and hand-triggered catalogue events move it; nothing reads it in a game without war.
- Nation ratings: `play_difficulty`/`play_difficulty_note` on each realm come from `difficulty*` or `simple_difficulty*`, set in `_recalculate_all_realms`.
- `load_scenario_config` now caches by file time like the quiz: **treat the result as read-only**.

**Screens**
- Setup: "1 · Game complexity", "2 · Scenario", "5 · Scenario numbers"; `.only-full`/`.only-simplified` follow `data-complexity` on the page. Phone (`realm.html`): the Quiz tab, War room, motion form, Vitality bar and Rationing decree are not rendered in the simplified game; `#food-forecast` and `.mission-hint` are added. Admin, projector, Guide and report follow `rules`. The Guide's nation stats now come from the config plus the bonus.
- `setHtml(el, html)` in `common.js`: lists polled once a second are only rebuilt when they change.

**Bugs found in the review and fixed (each has a regression test)**
- In the Grand Plenary a **rejected motion still took effect**, including rejected Food Acts (`advance_grand_plenary_next` applied it whatever the vote).
- **A phone could act in another nation's name** by naming itself in `realm_id` and the victim in `sender_id`/`proposer_id`/`supporter_id`, for example emptying its silos with a trade to itself. `enforce_api_auth` now requires every nation named in the request to be logged in.
- **Players could run code on the projector and phones**: motion titles were inserted unescaped on the results screens (a title reaches the phones through Solaris' veto mission). Confirmed in a browser against the old script.
- **Trade offers and notes reached everyone** through `/api/state`, even logged out, although the news had been made private. `_trade_view`: the two nations see the offer; others only see that a trade was concluded (the map needs that).
- **Sounds of a new turn were lost** (`process_end_of_turn` and the famine saved an older `meta` over the cue), and their news carried the old turn's stamp. Cue type `siren` (famine, disasters) was silent everywhere, and `adminApp.triggerRoundCrisis` called a missing `synth.playSiren`, so the button reported a failure after succeeding. Now `synth.playCue`.
- **Advance Turn went past the last turn** (Turn 4) and even revived a finished summit. `/api/admin/turn/next` refuses, and the buttons become "End Summit" in the last turn.
- Screens rebuilt lists every second: "Read the terms" closed itself, the facilitator's seat dropdown shut, and a tap between press and release could be lost. `setHtml`.
- Restoring a save skipped past a running vote or debate (their clocks were not rebased) and charged an open quiz question as wrong. Now they resume; the question becomes the nation's next one again.
- A nation could vote on a motion that was not on the ballot. Catalogue events hit nations that are not playing. A blank trade amount was a server error. The projector drew the *oldest* six trades instead of the newest. `admin_remove_realm` filtered trades on keys that do not exist. Motion amount fields refused anything above 30 although the rule is "no cap". `/api/events` was open to everyone. Other nations' `quiz_next` was sent to everyone.
- **Aquila's public lobby note gave away its secret mission** ("wealthiest by 25 points"). Reworded; a test checks the notes.
- Text: the phone's hard-coded "5 minutes" of debate; the Guide's old quiz rules and motion limits; the README's old vote rule, quiz payouts and motions; "1 nations".

**Balance (`tools/simulate.py --simplified`, 40 games per row, no attacks)**

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

The Full game's rows match the figures measured before this round within noise (Standard with a good quiz was 8 / 50 / 42 %), so the bug fixes did not shift its balance.

The sim's delegations rarely pursue Val-Khor's public mission or Aethelgard's reserves, so those look harder than they are: `test_a_perfect_game_meets_every_mission` plays a full game that meets all twelve and ends Stable. Numbers for humans will differ, and nobody has played the Simplified game with real people yet.

**Open questions for the user** (not changed)
- The notes put the meal *before* the quick vote in Rounds 1 and 2 ("−20 Grain, then Quick Plenary"); the game votes first and eats afterwards, as it did before this round.
- Reset Sim returns the roster and passcodes to the config, while Start a new summit keeps them.
- `tools/simulate.py` models sensible and selfish delegations, not newcomers; the bonus may need tuning after a first real session (`complexities.simplified.starting_bonus`).

**Tests:** 288 (260 unit/API, 28 browser). New: `TestRulesAreKept`, `TestApiIsKept`, `TestDifficultySettings`, `TestSimplifiedGame` (including a scripted game that meets all twelve missions), `TestNationRatings`, `TestSimplifiedScreens`, and browser tests for the setup screen, a complete Simplified game, the projector and Guide, screens that refresh without closing what is open, the last-turn button and injected HTML.

## Update 2026-11-07: intuitive phone and deck, saves that really work
**Decision from the user:** the game should overwhelm through its complexity and possibilities, never through its UI. "Make sure that the autosave works." The projector is fine as it is and was left alone (only a connection bar was added).

**Join page and logins (`lobby.html`, `admin_login.html`)**
- All six nations fit on the first screen of a 360×640 phone. Tap a nation for a sheet with its details and the passcode field, at the top of the screen so the keyboard never covers the button. The field is plain text with dots drawn by CSS (`-webkit-text-security`), because a password field makes phones offer to save a password.
- A logged-in phone gets "Back to <nation>" (decided on the server: `my_realms`). `has_auth_*` cookies are gone. `/?login=<id>` when already in goes straight to the console; a phone waiting at the passcode prompt polls `my_realms` and returns by itself if its game is restored. A stale login arrives with `&again=1` and the sheet says why it asks again.
- A full delegation explains itself in the sheet (no more `alert()`). The facilitator login says where to find the passcode; `app.py` prints it at start.
- `/admin/cards` (`cards.html`): one printable card per nation with a QR code to `/?login=<id>` and the passcode. Fits one A4 page.

**Phone console (`realm.html`, `realm.js`)**
- `clockStage(meta)` in `common.js` (ready, intermission, running, paused, timeup, other) drives the phase card, which now says when the game has not started or is paused. Actions before the clock starts stay allowed as before; only the words changed.
- The ✕ is gone: the `?` button opens `openHelp()` (how a turn goes, where things are, Guide, sound switch, leave). `explain(key)` on every number. First-time card (`localStorage.summit_welcome_seen`). `showSheet` in `common.js`.
- Order: latest news and numbers near the top, then goals, decrees, war room, and "About <nation>" (the difficulty note moved out of the public mandate). Vitals are three compact tiles, with bars turning amber below 50 and red below 25.
- Number changes show a mark on the tile (`_noteChange`), and a toast if another tab is showing. Decrees show `.cannot` and why (`data-needs`).
- Trade: offers to you first and hidden when empty, "You have N", warnings in the summary (not enough stock, border-crisis transit loss), past offers listed, and toasts when an offer arrives or is answered (`_announceTradeNews`).
- Motions: the floor first; `#motion-builder` is its own screen behind "+ Propose a motion". Gallery rows are short. Form order: what it does (with the live preview), then the wording, then who may co-sponsor. Summaries of three templates were reworded in `scenario_config.json`. The badge only counts motions that still need a co-sponsor.
- World: News / The nations segments, an unread badge, pip legend, nations open for their public mandate.
- Vote: "For / Against / Abstain" (`.vote-for`…), the real countdown, plain words. It closes the wiki and scrolls up when a vote opens. A siege alarm (`#siege-alert`) is on every tab. The wiki bar has a clock. The debrief card uses classes (`.verdict-card`).
- **Phones no longer chime for other nations' decrees and trades** (new cue type `decree`; the projector still plays it). A cue's toast is skipped for `decree` and `trade`.

**Command deck (`admin.html`, `admin.js`)**
- `renderNow(state)`: the sticky panel on every tab with what is going on, what comes next, the clock and the buttons. Other buttons were removed: header Advance Turn, Chime, the setup banner, "Execute End of Turn". Who still has to vote is listed; things waiting elsewhere appear as `.now-alert` links.
- Tabs renamed: Run the game, Motions, Events, Nations' numbers, Players & passcodes, Saves. `showTab` keeps the tab in the address (`#tab-…`).
- Run tab: "Before you start" checklist with seats and passcodes until the game starts (and a nudge if the passcodes are still the guessable defaults, `pins_are_default`), then "Who is connected"; a game timeline; the clock console; room sounds.
- Removed (each was redundant or broken): Reset Sim and its modal (`/api/admin/reset` stays, for tests; **Start a new summit** on the setup screen is the one way to start over), the "3/4/5/6 nations" buttons (they took the first N nations in config order, against the advice on the setup page; the engine call stays because tests use it), Add Delegation (`/api/admin/realm/add` removed: it made nations with no missions or map place), the Edit modal (its flags are in the modifiers; `private_agenda` was shown nowhere; "starving" was overwritten on every recalculation), delete-nation ✕.
- Setup: steps numbered by CSS counters, one "Fine-tuning" section closed by default with its values in the title, unsaved changes are shown (and leaving asks), a sticky action bar. "Continue to the command deck" before a game; "Start a new summit" only once a game is under way. The nations table turns into cards on a phone.
- Every deck tab and the setup page now fit a phone (`.deck-grid`; the inline two-column grids used to overflow).

**Saves: bugs found and fixed (`autosave_probe` output is summarised here)**
- An hour of idle polling (a projector left open) pushed every real save out of the list, including the "Before server restart" one: 12 slots, and a fresh idle game saved itself every 5 minutes. Now: only games in progress that have changed are auto-saved (`autosave`: fingerprint of `dump_all`), and automatic (24) and deliberate (20) saves are kept separately (`Database.add_autosave`, columns `kind`, `game_id`, `turn`, `phase`, migrated for old databases).
- The browser copy had the same flaw, worse: every page load and every 5 minutes it stored the current game, so after a restart the "newest copy" the README told people to restore was the empty new game. It also failed silently when out of room. Now see `keepBrowserCopy`.
- `/api/admin/reset` kept no copy. A restored clock ran at once. A failing autosave broke the state poll (now caught and reported in `save_status.error`). `game_in_progress` missed a game concluded in Turn 1.
- New: `engine.interrupted_game()` / `dismiss_interrupted_game()` / `POST /api/admin/resume/dismiss` and `#resume-banner` (also from the browser's copy); a prepared but unstarted game survives a restart (kind `setup`); checkpoints at the start of each turn and at the end. `AUTOSAVE_SECONDS` env var for the tests.
- **`test_summit.py` used the real `summit.db`** (app.py opens it at import; `TEST_DB` only covered the test's own engines): every test run reset the real game. It now sets `SUMMIT_DB_PATH` to a temp file first.

**Other fixes:** a declined change of seats or a refused passcode stayed on screen as if it had worked. "1 seats". Setting the clock before the start counted as the game being in progress. A nation activated after the lobby loaded did not appear until a reload. A nation taken out of the game left its phones stranded. Toasts swallowed taps on what was under them. Toasts and news in jargon ("Plenary Session Convened", "Sovereign ballot recorded").

**Open questions for the user**
- ~~Phones do not state the verdict's exact thresholds.~~ Answered 2026-11-07: the Simplified game states them, the full game does not (see the last update).
- Not tried on physical phones: everything was checked in Chromium with phone viewports and touch emulation. The on-screen keyboard behaviour in particular should be checked on a real iPhone.

**Tests:** 331 (289 unit/API, 42 browser). New: `TestSaves` (rewritten), `TestJoiningAndScreens`; browser tests for the join page on a small phone, a full delegation, the phone's states and help, what needs an answer coming first, the vote, the deck's panel through a whole game, the setup page, passcode cards and no sideways scrolling on any screen. `test_a_crashed_server_loses_nothing_and_the_room_gets_back_in`, `test_a_wiped_hosted_server_can_be_restored_from_the_browser`, `test_declining_the_interrupted_game_is_remembered` and `test_autosave_really_runs_during_a_game` run against a real server process that is killed and started again.

## Update 2026-11-07 (later): Czech, map traffic that follows trades, mountains that stay put
**Requests from the user:** add Czech; on the projector, traders should reflect reality ("in the beginning there should be basically no trade"); the mountains moved during the tour.

**Map (`static/js/map.js`)**
- The old carts (one per road, always moving) are gone. `buildRouteNetwork` makes a graph of the roads and Aquila's sea lanes; `route(a, b)` is Dijkstra between two capitals. `syncCaravans()` sends one caravan per **accepted** trade (wagon on land, small ship at sea, in the sender's colour), at most 3 per pair of nations; trades seen at the first look start at a hashed point of their way, new ones at the sender. A new game empties the roads. Ships in harbour/at sea: `shipsAtSea` grows with the number of trades (none at the start). A trade's golden arc shows for 40 s after it happens, then fades.
- Mountains slid because sprites were lifted by their height through the tilted camera although the terrain is a flat picture: sprites are now placed at `project(x, y)` (no lift); same for the tornado's ground point.

**Languages (`i18n.py`, `static/js/i18n.js`, `translations/cs/`)**
- English stays the source everywhere; the engine, database and saves are unchanged. Translation happens on the way out: `translate_response` in `app.py` (runs last, after releasing the state lock) translates HTML pages (text between tags and `title/placeholder/aria-label/alt/data-*` attributes, never scripts or SVG) and `/api/*` JSON (except `/api/wiki*`, which has its own Czech articles, and the save export). In JSON, values under code names (`id`, `phase`, `status`, `*_id`, `*_tier`…, see `_CODE_KEYS`) are left alone when they are words or lists of words; dicts under such names are still read (`mission_status`).
- `static/js/i18n.js` is loaded in the head only when a screen is not English; a MutationObserver translates text nodes and `title/placeholder/aria-label` as scripts write them; `window.tr` for the map's canvas labels. Browser catalogues: `/i18n/<lang>/public.js` (everyone) and `/i18n/<lang>/deck.js` (facilitator only; empty for others). `window.i18n.misses` lists what could not be translated (for checking a language by hand).
- Matching rules (both sides): exact text; symbols around it; typed placeholders (`n`=number, `amount`=number+resource, `name`/`*_name`=capitalised name, other=free text that cannot run into the next sentence); the sentences of every multi-sentence entry are learned on their own; then splitting on sentences, `;`, ` | `, ` · `, `: `, `, `, ` → `, ` — `; then "structural" patterns with hardly any words (`{x} ({y})`). Czech plurals `{n:one|few|many}`.
- Language choice: `settings.language` (setup screen, default `game_settings_defaults.language` = en, kept across `fresh_start` and restores, ignored by `_setup_differs_from_config`), device cookie `summit_lang` via `/lang/<code>` (redirects only to a path of this site). `/api/state` carries `language`; `followLanguage(state)` in `common.js` reloads a screen whose language changed. Switches: join page, phone help sheet (copied from `<template id="language-switch">`), page header, projector settings.
- Script logic no longer reads English sentences: battle odds have a `tone` (`battle.odds_tone`), the verdict colours use `continental_grade`. The map's quality chips are *Sharp / Balanced / Light* (High/Low already meant tiers). The report shows words instead of status/choice/outcome codes.
- Czech wording follows the facilitator notes: stát/státy, delegace, kolo, pracovní část, Shromáždění, Velké plénum, návrh/rezoluce, předložit, podpořit/spolunavrhovatel, opatření, veřejný mandát, tajná mise, facilitátoři (also for "game masters"), obilí/jádra/hedvábí/vojsko/vitalita/reputace/stabilita. News use present tense or "země X", so the English nation names need no Czech grammar. Names stay English. Quiz options that expand the abbreviation AC keep the English with a Czech gloss.
- Tools used to build and check the catalogues lived in the session scratchpad (not in the repo): a JS tokenizer listing every string in the scripts, a crawl of every rendered page, and a Playwright run of a whole game in Czech (full and simplified) that reports any English left on screen plus a dictionary check. The last run found none.

**Tests:** 353 (289 unit/API, 20 language, 44 browser), all passing. New: `test_i18n.py` (translator rules, catalogue coverage of missions, scenarios and quiz, no secrets in `public.json`/`deck.json`, placeholders consistent, language choice per game and per device, safe redirect, codes untouched in JSON, deck catalogue only for the facilitator, language kept across restart and restore, Czech report); browser tests `test_czech_chosen_on_the_setup_screen_and_one_phone_in_english`, `test_the_map_shows_traffic_only_for_real_trades`.

**Follow-up the same day (user):** "Everything should be translated, including the names. The exact thresholds should be known in the simplified version, not in the full game."
- Czech names: nations keep their own root and lose the English words (*Sylvanský konkordát, Železný Val-Khor, Solariská nadvláda, Umbrijská enkláva, Aquilská námořní liga, Aethelgardské dominium*; upper-case forms for headlines), towns (*Aethelhrad, Kamenná Stráž, Khorská Brána, Khorská Hlubina, Železné Údolí, Slunný Vrch, Jitřní Trh, Kořenov, Krbokořen, Dubové Jezero, Lucernopád, Závojná Rokle, Soumračná Studna, Halkyonský Přístav, Slaná Brána*; Helion and Garrowmere are names already), *Velkohvozd*, *Mlžná propast*, *Věžopedie*, years in *PK*. Invented personal names stay (Hadrek Vorn…); *Sunmaker* is *Slunotvůrkyně*. Czech texts were rewritten so the names take the right case, and sentences where a name would need a case it cannot take use "stát X" ("PORÁŽÍ STÁT…", "táhne na stát…", "Připojit se: X"). The map's `mapText` translates every label it draws. Quiz q01 asks about "PK" with Czech distractors that also start P… K….
- Verdict thresholds: `verdict_rules` (rules flag, true only in `complexities.simplified`). With it the phone's `?` help has "How the continent is judged", the Grain/Standing/Stability explanations say what each needs, and the Guide (Turn structure tab) lists the three verdicts. The full game is unchanged. Tests: `test_changing_complexity_before_play_swaps_the_bonus_without_a_new_game` (flag), `test_the_phone_explains_itself` (absent in the full game), `test_simplified_game_from_start_to_finish` and `test_simplified_projector_and_guide` (present). Still 353 tests, all passing.
