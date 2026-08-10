# Brief: building & publishing sites with our AI Employee (verified 2026-08-10)

## Who
Software Developer (persona Roman). Capabilities doc: "You build complete, working apps and websites
for people who don't code - websites and landing pages (business, event, portfolio, idea), small apps
and tools (booking/signup forms, trackers, calculators, dashboards), games, apps that remember things."
Friendly, plain language, never tech-speak. NOTE: design app + design skill DISABLED on default brand
2026-08-10 -> teach ONLY the Software Developer path.

## What it produces
- single self-contained HTML page (deploy/static, 1 file, 5MB) -> instant CDN URL
- multi-file static site HTML+CSS+JS+images, multi-page (deploy/app, max 200 files, 5MB/file, ~80MB)
- framework app (Next.js/SPA) - build runs upstream
- app with real database (signups/bookings/posts) via manage-databases: free tier sleeps, paid ~$7-17/mo

## Flow (what the student experiences)
1. types request in chat with Software Developer
2. employee asks 0-2 clarifying questions max
3. creates workbench project (system of record) + launches a JOB
4. replies ONE line "working on it" - NO LINK YET (every older link is broken/stale)
5. sandbox: builds -> commits to private repo -> deploys -> takes a 1280x720 screenshot as cover ->
   records a version -> QA pass: opens the live link in a browser and walks the flows before saying done
6. mid-build questions appear as interactive QUESTION CARDS in chat (answer resumes same job)
7. done -> result posts into chat live; in-chat BROWSER PANE opens on the live page
8. user gets a STABLE link workbench.42bucks.com/p/<slug> (302 -> current version)

## Starter prompts shipped in the product (use verbatim)
1. "Сделай простой сайт для моего бизнеса"  (Build me a simple website for my business)
2. "Сделай лендинг для моего нового продукта" (Make a landing page for my new product)
3. "Сделай страницу записи, которая сохраняет людей в лист ожидания" (signup page -> waitlist)
4. "Сделай одностраничник для кофейни: часы работы, меню, карта и кнопка «Забронировать стол»"
5. "Сделай лендинг вебинара с таймером обратного отсчёта и формой сбора email"
6. ITERATION: "Поменяй герой на зелёный и добавь блок с тремя тарифами"

## THE most important student rule: ITERATE, DON'T REBUILD
"Change the colors / add a section / fonts broken" = continue the SAME job (clarify), never start a
new build. Starting fresh throws away the session + working files, is slower, costs more, and the
correction often regresses other things. If the GOAL changes entirely -> cancel + relaunch.

## Limits / gotchas
- Job ceiling 3 hours; idle reaper 15 min of zero output; static deploy live instantly, app deploy <15s
- 5MB/file, 200 files, root index.html REQUIRED (else 400)
- Deploy currently debits 0 credits; code-job spend is capture-only (nobody charged today). LLM usage
  and paid databases DO cost. Monthly per-user credit cap can block chat.
- EVERY deployed URL IS PUBLIC AND UNAUTHENTICATED - never put private data on it
- Each publish = NEW immutable URL; only the Workbench stable link stays constant
- NO CUSTOM DOMAIN in v1 ("platform-default URL only"; manage-domains can BUY a domain and edit DNS
  but explicitly does NOT wire it to a site, no SSL, no delegation) -> THIS IS WHY the course still
  teaches Lovable/hosting for a real client domain
- Iframe-hostile pages render blank in the preview pane - open in a new tab
- Vendor names are never spoken by the employee ("the deploy", "your page", "the preview")

## Ownership / export
- private git repo per project (invisible to user)
- Workbench -> project -> Download code (ZIP)
- "Put my <project> on GitHub" -> connect GitHub -> job mirrors the repo (only time a repo is surfaced)
- files delivered into chat render as downloadable cards

## UI surfaces to describe in lessons
- in-chat BROWSER PANE (right rail, real tabs, back/forward/refresh/open-in-new-tab). Empty state:
  "When your AI Employees deploy a page or launch one of their apps, it will show up here for you to
  interact with."
- JOBS PANEL: queued/running (blue), awaiting_input (pulsing amber), done (green), failed (red)
- QUESTION CARD when the job needs an answer
- DEV WORKBENCH app (workbench.42bucks.com): project grid with screenshot covers; project page =
  Open live site, copy link, Request a change, Download code, Plan, Put this on my GitHub, Work log,
  Versions with Live badge + RESTORE, Monitoring (uptime, "Responding/Not responding"), Databases
  (pause/resume, "~N credits/hr")
- empty state: "Ask Roman, your developer, in the chat to build something for you"

## Lesson split suggestion
1 easiest first build (prompts, rhythm, no instant link) | 2 chat -> live link (deploy, stable link,
preview pane, public warning) | 3 changing what you built (iterate same job, question cards, versions
+ restore, monitoring) | 4 owning it (download ZIP, GitHub, database for signups, honest limits)
