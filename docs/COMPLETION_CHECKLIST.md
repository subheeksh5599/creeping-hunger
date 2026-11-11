# Completion checklist

Researched 11 Nov 2026 for the Mozilla Otari Hackathon, Devs Wilding. Deadline is today, 11 Nov 2026, 10:29 PM IST. This file compares Creeping Hunger with privacy-policy tools that actually shipped, then lists what we still have to finish. It is a build checklist, not a marketing page.

## Where we stand

> This is the plan written at the start of the day. Since then the README, FEEDBACK.md, landing page, shadcn dashboard, Render deploy, screenshots, cache, quote highlighting, tips block, compare view and time-spent line have shipped; see the README's live status table. Still open: the demo video, making the repo public, filing the Otari issues, and the submission reply.


The backend pipeline, MCP server, Firefox sidebar, hostile test page, and sample event logs already exist under `/workspace/creeping-hunger`. The planned path is real: find a product's privacy policy, extract practices with an open-weight model behind a prompt-injection guardrail, research with Otari web search plus our MCP tools, run readability and an archive diff in Otari code execution, then judge with a routed model and a fallback. That is more machinery than almost every shipped "paste a policy, get a score" extension.

We have not finished the product surfaces that make a submission look done. There is no README, no FEEDBACK.md, no landing page, and no dashboard. `web/index.html` is a fallback reviewer, not a homepage. The repo is still meant to stay private until the product works. Store listing is out of reach today. We have sample logs for Fitbit Charge 6 and the hostile page, but no written check of those claims against the live policy. Competitors who "finished" did it by shipping a one-click path, a documented install, a public repo or store listing, and a video of the live product. That is the gap this list is for.

## Comparison

| Project | What they shipped | How they finished | Install and proof | Links |
| --- | --- | --- | --- | --- |
| *Privacy Not Included, Mozilla Foundation | A buyer's guide, 2017 to 2026, with a *Privacy Not Included warning label, a reader Creep-O-Meter, and a public rubric. Original reviews used public docs and company questions, not a lab. On 11 Aug 2026 the guide format retired and the work moved to hand-tested Product Reviews of popular items in *Nothing Personal*. Mozilla says archived reviews reflect the time published and are not current. | They limited the catalog to popular products, reused the same review shape, and published the methodology. They did not try to score every site on the internet. | The guide itself was the product. Webby awards and press followed the repeated, readable format, not a model demo. | ["Privacy Not Included Has Moved"](https://www.mozillafoundation.org/en/nothing-personal/privacy-not-included-sunset/), [wiki / methodology](https://wiki.mozilla.org/Foundation/Privacy_not_included) |
| ToS;DR | Website, public API, and browser extensions that show A to E grades plus short points. Firefox listing has historically been well reviewed, about 4.6/5 from roughly 178 reviews, though the add-on has had store disruptions in late 2026. `tosdr/browser-extensions` has 513 GitHub stars. | They did not auto-grade new sites with an LLM. Reviewers annotate quotes, curators approve, and a public algorithm turns point balances into a grade. The extension mostly displays existing grades. | Official store listings plus a documented build-from-source path. The grade math is public. | [tosdr.org](https://tosdr.org), [extensions repo](https://github.com/tosdr/browser-extensions), [grade algorithm](https://docs.tosdr.org/phoenix/how-are-classifications-calculated) |
| Polisis / PriBot, Harkous et al. | A public site and Chrome/Firefox extensions, 2018. Polisis maps a policy into labeled segments. PriBot answers free-form questions. USENIX Security 2018 paper. Reported 88.4% accuracy against OPP-115 privacy-icon labels. The extensions later went stale. | They shipped a research demo with a paper, a live site, and a stated eval. Scope was classification and Q&A, not a shopper's verdict. | [pribot.org](https://pribot.org/), plus the paper. Accuracy was measured on a public dataset, not asserted in a store blurb. | [pribot.org](https://pribot.org/), [USENIX paper](https://www.usenix.org/conference/usenixsecurity18/presentation/harkous) |
| Trust Layer, Vishnu | Chrome extension, store version 0.4.0, 14 Feb 2026. Click the icon, find the policy link, send only that URL to a backend, get a 1–10 score, a SAFE / CAUTION / HIGH RISK label, category chips, and short bullets. 8 ratings, 5.0. Has a privacy policy. Says it is not a lawyer and can be wrong. | They cut the product to one click and a short verdict. One commercial model, no archive, no breach check, no open-weight split. | Chrome Web Store. Backend repo and PRIVACY.md are public. | [Chrome listing](https://chromewebstore.google.com/detail/trust-layer/pdaeghgikdefhjmpfnknponehopmeenc), [backend PRIVACY.md](https://github.com/Zorrojurro/trust-layer-backend/blob/main/PRIVACY.md) |
| Privacy Pal, Lakshya Upadhyay | Firefox add-on v1.1.0, 19 Jul 2025, with a GitHub repo. One-click analysis of the current page, a verdict, a 1–10 score, categorized points, and on-page highlighting of risky clauses. Claims it does not store analyzed policies. | A small extension with one visible affordance, highlighting, was enough to ship. | Firefox Add-ons plus load-unpacked instructions in the README. | [AMO listing](https://addons.mozilla.org/en-US/firefox/addon/privacy-pal/), [GitHub](https://github.com/hackbuddy1/privacy-pal-extension) |
| Privacy Guard | Chrome side panel that finds a policy, including PDFs, and analyzes it with a key the user stores locally. Gemini Flash is the default, with Claude or on-device Chrome AI as options. Results are cached locally. Users can paste a URL if auto-detect fails. About a dozen store users and no ratings at the time of this research. | They finished setup and the empty state. One-minute key setup, a paste fallback, and no hosted backend to keep alive. | Chrome Web Store. The listing itself is the install guide. | [Chrome listing](https://chromewebstore.google.com/detail/privacy-guard/hdlhdbcdjlnkflfinpofiampkjkpamcl) |
| Privacy Pilot, AI ATL 24 | Chrome sidebar. Scrapes the page for privacy/terms links, sends them to FastAPI, scores 10 GDPR/CCPA parameters, and shows quotes with links back to the source. Gemini 1.5 Flash with a Claude 3.5 Sonnet fallback. MongoDB cache, claimed 99% faster on repeat URLs. Won Google Cloud Overall. | They made one-click discovery work, showed evidence, documented fallback, and recorded the live sidebar on a real page. Extra browsers and in-document jump links went to "what's next." | Public GitHub and a YouTube demo on the Devpost page. | [Devpost](https://devpost.com/software/privacy-extension-your-privacy-rights-at-a-glance), [GitHub](https://github.com/AlexT101/privacy-pilot) |
| Meerkat Privacy, HackNYU 2025 | Chrome extension, Flask API on a VPS, landing page at meerkatprivacy.com, and a GitHub Releases install guide. GPT-4o-mini summaries and preference-based scores. Devpost video. | They deployed, wrote a homepage, and gave a manual install path because a store listing was not ready. | Landing page, GitHub Releases, Devpost writeup and video. | [Devpost](https://devpost.com/software/privacy-expert-chrome-extension), [landing page](https://meerkatprivacy.com) |
| TOS-ter, MEGA Hackathon 2023 Summer winner | A MERN web app. Upload or search a company's terms, GPT-3.5 summary and rating, MongoDB cache after ~20s first calls. Themed UI. The Chrome extension was listed as future work. They said some answers were wrong. | They shipped a complete web path instead of a half-built extension, and cached so the demo was usable. | Public GitHub and a Devpost video of the web app. | [Devpost](https://devpost.com/software/tos-ter) |

Two Firefox listings look finished and are not useful models. [Clarity Privacy Analyzer](https://addons.mozilla.org/en-US/firefox/addon/clarity-privacy-analyzer/) was last updated 2 Aug 2025, with no reviews and about one reported user. [PolicyThere Grade Checker](https://addons.mozilla.org/en-US/firefox/addon/policythere-grade-checker/) was last updated 10 Jan 2025, with about one daily user. A store page with a long feature list is not the same as a working demo.

Other web tools in this space, such as [Guard](https://www.webfolio.to/tools/guard) and [TrustScan](https://trustscan.dev/blog/best-privacy-policy-summarizers-2026), are paste-a-URL summarizers. They matter as UI references, score plus red flags plus a disclaimer, not as Otari-rubric competitors.

### Honest comparison with us

We are ahead of the shipped AI extensions on substance. Trust Layer, Privacy Pal, Privacy Guard, Meerkat, and TOS-ter mostly send policy text to one commercial model and return a score. Privacy Pilot is the closest hackathon peer, and even it stays inside a GDPR checklist plus a two-vendor fallback. We split extractor, researcher, and judge across open-weight models, check Have I Been Pwned, ToS;DR, and the archived PNI review, diff the policy against Wayback, and show a prompt-injection block on a hostile page. For this rubric, that is the right shape.

We are behind them on being done. Trust Layer and Privacy Pal are installable from a store. Privacy Pilot and Meerkat had a public repo, a narrated demo of the live UI, and in Meerkat's case a landing page and a deployed API. TOS-ter won without an extension because the web path actually worked on camera. We still need those submission surfaces. Judges here will score Otari feature use and the demo, not Chrome-store polish. We win if every rubric feature fires on camera, install takes a few documented steps, and we do not pretend to be a current Mozilla review or a lawyer. We lose if the recording is a slide deck, a localhost error, or a score with no sources.

## Checklist

Do the MUST items before the 10:29 PM IST deadline. NICE items help, but not if they steal time from a working demo, a public repo, or the writeups.

### MUST

1. Run a live review of a real product page, Fitbit Charge 6 is already in `samples/`, and a live review of the hostile test page, then replace or confirm the event logs in `samples/`.
2. In those runs, confirm the UI actually shows search/fetch, MCP calls to HIBP, ToS;DR, and the PNI archive, code-execution stats plus an archive diff, three distinct open-weight model roles, a prompt-injection block, judge fallback via the force-fallback control, per-step and total cost, and the install id sent as the Otari user for per-user budgets.
3. If any of those features is skipped, locally faked, or invisible in the UI, fix the live path or drop the claim. The rubric only counts features the app uses.
4. In the Otari dashboard, create the judge routing policy, attach the prompt-injection guardrail profile to the extractor, and turn on per-user budgets if those cannot be set from code, then write the exact clicks in the README.
5. Show a short quote or clause from the policy next to each red flag, not only a paraphrase.
6. Put one plain disclaimer in the sidebar, the web UI, the landing page, and the README: this is not legal advice, not a current Mozilla PNI review, archived PNI text can be outdated, and the score can be wrong.
7. Replace the current `web/index.html` stub's job as the public face with a real landing page that states what the tool is, shows one sample verdict, and links to Firefox install, the dashboard, the repo, and a short run guide. Keep a reviewer page, just do not make it the homepage.
8. Ship a shadcn dashboard that can replay a review, steps, models, costs, MCP hits, guardrail result, verdict, so the demo has a place to show history and spend.
9. Write `README.md` with purpose, four-step Firefox load-unpacked install, how to run the backend and MCP server, `.env.example`, Otari dashboard steps, the eight pipeline steps, and the disclaimer.
10. Write `FEEDBACK.md` with real problems found while building, and open those as GitHub issues once the repo exists.
11. Deploy the backend and MCP server to a public HTTPS URL, or a temporary tunnel, and put that URL in the extension's default settings so the demo does not depend on `127.0.0.1`.
12. Add screenshots of the sidebar verdict, the hostile-page block, the dashboard, and the landing page to `docs/` or the README.
13. Confirm `.gitignore` excludes `.env` and that no API key is in the tree.
14. Keep the repo private until the live path works, then make it public before 10:29 PM IST. The hackathon requires a public repo.
15. Do a silent timed rehearsal of the shot list below, and if a live review takes more than about a minute, have the finished Fitbit sample ready to open while it runs.
16. Prepare the submission reply for the sign-up thread to marcus+wilding@mozilla.org with the public repo URL, the 3-5 minute demo link, and the feedback/issues link. Do not send it until the user approves the draft.

### NICE

1. Cache completed reviews so a second visit to the same URL is instant. This was Privacy Pilot's main latency fix.
2. Highlight the risky sentence on the policy or product page, as Privacy Pal does, in addition to quoting it in the sidebar.
3. Hand-check 5 to 10 claims from the Fitbit sample against the live policy and write a hit/miss list in `docs/`.
4. Auto-discover privacy-policy links from the current product page when the user is not already on the policy.
5. Add a short "tips to protect yourself" block under the verdict, in the old PNI format.
6. Accept PDF privacy policies. Privacy Guard and some web tools already do.
7. Submit to addons.mozilla.org. Review will not finish today, so this is post-deadline.
8. Compare two products side by side in the dashboard.
9. Show a "time spent" figure next to cost, in the spirit of PNI's hours-of-research line.

## Demo video tips

The rubric asks for a 3-5 minute demo that is your own screen recording with your own voice. An AI-made video is not allowed.

**Opening, 20-30 seconds.** One sentence that Mozilla's *Privacy Not Included* moved in Aug 2026 from a broad guide to hand-tested reviews of a few popular products, and that its archived reviews go stale. One sentence that Creeping Hunger is a Firefox sidebar which reviews the product page you are on, using open-weight models through Mozilla.ai's Otari. Then open Firefox and the sidebar. Do not start with architecture.

**Happy path, about 2 minutes.** Open the Fitbit Charge 6 product page, or another real product you have already rehearsed. Click Review this page. Talk over the step list as models, tools, and costs appear. When the verdict lands, read the creep score and the warning label if there is one. Then point at a policy quote or red flag, the ToS;DR / HIBP / archived PNI row, the readability numbers and archive diff from code execution, and the total cost.

**Rubric proof, about 1-1.5 minutes.** Open the hostile test page and show the guardrail blocking it. Turn on force judge fallback and show the fallback chip and the model change. If the dashboard is ready, open that same review there and show the step, cost, and budget trail. Say the model names and their jobs out loud: extractor, researcher, judge.

**Close, 20-30 seconds.** Say the install path, load unpacked, four steps in the README. Give the public repo URL. State one limit: not a lawyer, archived PNI reviews can be stale, the score can be wrong. Stop. Do not add a roadmap.

What the finished projects actually did on camera or in their writeups:

- Privacy Pilot won a large AI hackathon by showing the sidebar on a real page, tying quotes to scores, and describing a real model fallback. They cut other browsers rather than demoing stubs.
- Meerkat started on a landing page so judges knew what they were looking at, then switched to the extension. They used GitHub Releases because a store listing was not available.
- TOS-ter cached slow model calls and still won with a complete web app. If Otari is slow, do not sit in silence. Narrate the steps, or cut to a finished sample after you start the live run.
- Trust Layer and the old PNI pages spend almost no time introducing themselves. Score, label, a few bullets, a disclaimer.
- Clarity and PolicyThere published add-on listings with almost no users and no public proof of a working demo. A store badge will not help tonight. A working recording will.

Rehearse once with a timer. If you go past five minutes, cut the dashboard tour or the second fallback run. Keep the live product review and the hostile-page block.
