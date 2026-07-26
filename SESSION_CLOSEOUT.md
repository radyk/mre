HOTFIX SESSION CLOSE-OUT
The cockpit honors ?schedule= (and gets a picker)
2026-07-26

Repo: C:\dev\mre, branch master. Scope: cockpit frontend + its harness. No
solver, model, contract or API change. Python suite untouched and green.

======================================================================
SUMMARY
======================================================================
An explicit ?schedule= in the URL is now authoritative: the cockpit loads that
board, leaves the param alone, and says so by name when the id does not exist.
The header identity chip became the schedule switcher, so nobody edits a URL by
hand again.

  CU1  the param wins  -> pinned boots are never auto-followed; an unknown id
                          is a NAMED error over the schedule list, not a swap
  CU2  the picker      -> the strip's `solve #N` chip opens the registry
                          listing, newest first, rolling vs monolithic tagged
  CU3  diagnosis       -> where 87c705b9 came from, stated, not guessed

======================================================================
CU3 -- THE DIAGNOSIS (stated first, because it explains CU1)
======================================================================
87c705b9-85fc-4788-92c3-f90f9ab1e59a IS in the registry. It was registered at
2026-07-26T19:57:35Z, forty-four minutes AFTER rolling-279dec02-411 (19:13:10),
so it simply post-dates the listing the founder read.

Who mints it: NOT dev_api.ps1. That script only generates _data/mrd and starts
uvicorn -- it registers nothing. dev_cockpit.ps1 (terminal 2) is the minter: on
every boot without -Resume it submits _data/mrd and solves it synchronously,
then caches the new id in _data/.last_schedule. That file currently holds
87c705b9-85fc-4788-92c3-f90f9ab1e59a -- the fingerprint of the last dev restart.

Why that mattered. main.js boots, resolves the schedule, paints, and then runs
installFreshnessWatch(...).check() IMMEDIATELY. That watch (Session 4.4 CU2)
follows the newest live schedule in the whole data root whenever there is no
uncommitted planner state -- which on a fresh page load is always true. So the
newest row won, and on the dev loop the newest row is whatever the last
dev_cockpit.ps1 boot solved. The deep link never had a chance.

No stale-id leak into default resolution. resolveScheduleId's no-param path
(schedules[0] of an oldest-first listing) was never reached here, because the
param WAS present. That path has its own oddity -- it picks the OLDEST row and
is then corrected by the auto-follow reload -- which is noted and deliberately
LEFT ALONE: it is not the CU1 root cause and fixing it is not a hotfix.

======================================================================
CU1 -- THE PARAM WINS
======================================================================
An explicit ?schedule= now marks the boot `pinned`. A pinned tab is offered the
newer schedule in the existing dismissible banner and is never yanked; the URL
is left exactly as it was.

The one param the app writes itself is the LANDING of an auto-follow (4.4 CU2
reloads onto the newer id). Treating that as pinned would end the follow chain
after one hop, so it is explicitly not pinned -- read from the same
sessionStorage handoff the 4.4 "Switched to the new schedule" toast already
uses. A tab that followed once keeps following; a deep link never follows at
all. deeplink.spec.mjs proves both directions, including a second resubmit
landing on an already-followed tab.

An id this data root has no schedule for now renders an honest floor:

    no schedule rolling-nope-000 in this data root
    Nothing was loaded in its place. Pick a registered schedule:
    [ ...the schedule list... ]

It names the id, does not render a board, does not rewrite the URL, and does
not claim to still be loading (the strip's placeholder is replaced). The
recovery list is the same renderer the picker uses, so the two surfaces cannot
drift apart.

CONSEQUENCE, stated plainly: three Session 4.4 CU2 tests in cockpit.spec.mjs
asserted auto-follow from a boot that carried ?schedule=. Under CU1 that is now
the pinned case. They were retargeted to a new bootUnpinned() helper -- which is
what those tests were always about (a planner's own tab, not a deep link) -- and
the uncommitted-state test moved with them, so it now proves the uncommitted
rule rather than being carried by the pinning. No 4.4 behaviour was dropped.

======================================================================
CU2 -- THE PICKER
======================================================================
The strip's identity chip (`contract 1.8 - solve #9 - 03:13 PM`) is now a
button. Click it and the registry listing drops down, newest first, each row
carrying: short id, kind tag, created_at (date AND clock -- the dev root holds
several days of solves), status. The bound row is marked `current`, not hidden.
Selecting a row navigates; the URL becomes the chosen id and other params
(theme, api, ask) survive. Escape and click-outside close it, changing nothing.

Rolling vs monolithic, honestly. The registry has no sliced column, so the tag
is read from the two STRUCTURAL namings the sliced path itself mints:
src/mre/api/app.py registers `rolling-<run_id[:12]>`, and
rolling_horizon.prepare_plant names its snapshot `snap-rolling`. A monolithic id
is a uuid4, whose alphabet cannot spell "rolling", so the read has no false
positives. A registry `sliced` column is the durable fix and is NOT taken here
-- it is a schema change, recorded in docs/04 as such.

======================================================================
FILES
======================================================================
  src/cockpit/src/schedulepicker.js   NEW -- two pure reads + the shared list
                                      renderer + the dropdown mount
  src/cockpit/src/main.js             pinned resolution, the not-found floor,
                                      the chip-as-button, freshness gating
  src/cockpit/src/api.js              the ?schedule= contract, documented
  src/cockpit/src/cockpit.css         picker + list + not-found, token-based,
                                      both themes
  tests/cockpit/schedulepicker.spec.mjs  NEW -- 7 pure-logic specs (logic
                                      project, theme-free)
  tests/cockpit/deeplink.spec.mjs     NEW -- 5 specs x 2 themes: pinned wins,
                                      not-found floor + recovery, the unpinned
                                      auto-follow chain, picker open, picker
                                      select
  tests/cockpit/cockpit.spec.mjs      bootUnpinned() + the three retargets
  tests/cockpit/fixture-server.mjs    unknown ids now 404 on the document
                                      routes (they used to serve the base
                                      fixture, which made CU1 untestable)
  tests/cockpit/playwright.config.mjs the two new specs registered
  CLAUDE.md                           quick reference: ?schedule= + the picker
  docs/04-design-history.md           amendment appended

======================================================================
VERIFICATION
======================================================================
  pytest              1487 passed, 202 skipped (10m16s) -- untouched by this
                      session, run to prove it
  cockpit harness     195 passed, 0 failed (2.8m), light + dark + logic
                      (178 before this session + 17 new = 195; nothing was
                      deleted -- the three 4.4 tests were retargeted in place)

  LIVE, against the founder's own _data root (real API on :8000, built cockpit
  on vite preview :5176) -- the exact URL that misbehaved:

    url    : /?theme=light&schedule=rolling-279dec02-411   (unchanged)
    bound  : rolling-279dec02-411                          (the rolling board)
    pinned : true
    banner : the newer 87c705b9 is OFFERED, not taken
    tray   : the beyond-horizon tray rendered (it really is the rolling doc)

    picker : all 10 registry rows, newest first, rolling-279dec02-411 tagged
             ROLLING and marked CURRENT, the other nine MONOLITHIC
    fake id: "no schedule rolling-nope-000 in this data root" over a 10-row
             recovery list, URL unchanged, no board

======================================================================
CARRIED / NOT DONE
======================================================================
- The no-param default still resolves to the listing's FIRST (oldest) row and
  is corrected only by the auto-follow reload. Left alone: out of scope, not
  the CU1 cause.
- Rolling vs monolithic is a naming read, not a registry fact. A `sliced`
  column on the schedules table is the durable fix.
- The picker shows the short id, not `solve #N`: the LISTING carries no
  generation (only /meta does), and an invented ordinal would be a lie.
- The standing parallel-load screenshot-flake class saw one member trip once
  during this session (cockpit.spec.mjs CU5 zoom, green in isolation and green
  on the next full run). No new member added.
