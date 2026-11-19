# Hypotheticool Short formats

Every Short is one of three formats. Store the format in the topic JSON as `"format": "what-if" | "would-you-rather" | "pick-a-scenario"`. Older topic files with no `format` field count as `what-if`.

## Rotation (Shorts only; the weekly long video is always What If)
Repeat this 4-step cycle: **what-if → would-you-rather → what-if → pick-a-scenario**.
To find the next format, sort the Short topic files in `pipeline/topics/` and the claims in `pipeline/claims/` by post date/time and take the latest one that has a format (a claim file's first line can start with `format: <name>`). Then use the next step of the cycle. If two runs collide on the same slot, the claim file decides.

## Market research: do this BEFORE choosing any topic (Shorts and the long video)
The goal is to pick topics that are already proven to pull views, then make our own accurate, original 3D version. Spend about 15–25 minutes on this and use many searches.
1. **What's working in this format right now.** Use WebSearch/WebFetch to find the most-viewed recent Shorts and videos for the chosen format, e.g. "what if" science shorts, "would you rather" space/science, and "pick a planet/scenario" shorts. Check YouTube search results, the Shorts tabs of the top channels in each niche, and pages that list viral Shorts. Note titles, view counts, upload age (views per day matters more than totals), hooks and thumbnails. Look for topics and angles that keep repeating among the big hits.
2. **What people are searching and talking about.** Check Google Trends and trending-topic pages, this week's science and space news, and popular threads on Reddit (r/space, r/askscience, r/whatif, r/WouldYouRather, r/nostupidquestions) and similar communities. Prefer a topic with rising interest.
3. **Our own results.** Use Metricool analytics (getAnalyticsAvailableMetrics + getAnalyticsDataByMetrics, blogId 8192121, YouTube) to see which of our posts got the most views, watch time, likes and comments. Do more of what works for us (themes, formats, title styles) and less of what flopped.
4. **Pick.** Choose the topic with the best mix of proven demand + rising interest + fit for our channel (science, showable in 3D, 100% verifiable). Never copy another creator's script, title or visuals; only use the idea as a starting point.
5. **Log it.** Write pipeline/research/<post-date>-<slug>.md with: the format, the 5–10 best examples you found (title, channel, views, age, URL), trend signals, our own analytics takeaways, the 2–3 runner-up ideas, and why you picked this one. Commit it with the video. Later runs read the latest 3–5 logs first so research builds over time (reuse good runner-up ideas that aren't taken yet).

## Visual accuracy (applies to every video)
Graphics must be as accurate as the narration. Use the real-data assets in kit.py:
- **Planets and moons:** `kit.earth()` (real Blue Marble day map, real city lights on the night side only, real clouds, ocean glint, terrain relief; `face_lon` picks which longitude faces the camera, e.g. -80 for the Americas, 15 for Europe/Africa, 100 for Asia; aim it at the region the line talks about) and `kit.moon()` (real LRO map, near side toward Earth). Also `kit.planet('mars'|'jupiter'|'saturn'|'mercury'|'venus_surface'|'uranus'|'neptune'|'moon', R, tilt_deg)` (Saturn's rings use the real ring profile) and `kit.sun_sphere()`. Use real axial tilts (listed in planet()'s docstring). Never use the old procedural `*_procedural` versions for real bodies; they're only for fictional or alien worlds.
- **Sky:** `kit.world()` is a real Milky Way star map. Use `world(real=False)` only for stylized or abstract shots.
- **Spacecraft:** use the official NASA model whenever one exists: `kit.nasa_model('<folder name>', size, 'X')` (catalog: pipeline/assets/nasa_models.txt, e.g. Hubble, ISS, JWST, Voyager, Apollo Lunar Module, Saturn V, Space Shuttle, Cassini, Juno, Parker Solar Probe, Perseverance). `kit.hubble()` now loads NASA's Hubble. Use `kit.heat_glow(root, [(frame, strength), ...])` for reentry heating. Only build a custom model when NASA has none, and match real photos (shape, colors, proportions).
- **Physics on screen:** lighting comes from the Sun's real direction (day and night sides consistent between shots), and relative sizes and distances are true or explicitly labeled "not to scale". Real colors, not invented ones. Show the actual region, object or event the line mentions, never a generic stand-in when the real thing can be shown.
- **Detail:** keep planets big in frame when they're the subject (the 8K maps hold up in close-ups), and add slow realistic motion (planet rotation, cloud drift, gentle camera moves). Check every still against a real NASA/ESA photo of the same thing before the full render.
- **Credits:** the post text must end with the credit line in pipeline/assets/CREDITS.md (the planet textures are CC BY 4.0, so attribution is required).
- **Setup:** `pip install --break-system-packages DracoPy pygltflib` is required (NASA models are Draco-compressed; kit decodes them once into /home/claude/nasa_cache).

## Rules for all formats
- ACCURACY IS #1. Every claim is backed by at least two reputable sources (NASA, ESA, NOAA, USGS, universities, peer-reviewed summaries, major science outlets). Hedge where the science is uncertain. Options must be real-science hypotheticals, never made-up "facts".
- Hook first (line 1 = punchy true payoff under 8 words over the most dramatic shot), seamless loop (the last line flows back into line 1 and the last shot matches the first), calm pacing (at most one camera cut per scene), the same voice and pace, and 3D scenes built with kit.py.
- The last scene carries `{"type":"cta"}`. Never put `cta` in the same scene as `choice` or `options`, because they share the top of the frame.
- Captions stay in the lower third, so overlays only use the top ~25% and the middle.

## what-if
As before: line 2 asks "What if…?", then explains what would really happen. CTA uses the default text. Titles keep the "What if" framing. Hashtags include #whatif #shorts.

## would-you-rather (8–11 lines, ~45–60 s)
- Two science-based options that are interesting to compare, e.g. "a day on Mars or a day on the Moon", "swim in the Dead Sea or float on Titan's lakes".
- Line 2: "Would you rather <A> or <B>?". Keep a `{"type":"choice","a":"<A, max ~4 words>","b":"<B>"}` overlay on every scene from line 2 until the verdict.
- Next scene: "Comment A or B." with a `{"type":"prompt","text":"Comment A or B","pos":[0.5,0.42]}` overlay and a `{"type":"countdown","secs":3,"pos":[0.5,0.55]}` overlay. Make this scene at least 3.5 s; a pause or "Think about it" line helps.
- Then 2–3 lines on A and 2–3 on B, covering what it would really be like (temperature, gravity, air, danger, and so on). Each visual shows the option being discussed.
- Verdict line: which one is safer or better by the science, with `"win":"a"` or `"win":"b"` on the choice overlay. If it's a matter of taste, say so honestly.
- Last line loops back into the hook. Use `{"type":"cta","text":"FOLLOW FOR MORE WOULD YOU RATHERS"}` on the last scene with no choice overlay there.
- Title: "Would you rather <A> or <B>? 🤔 #shorts" (accurate, under 100 chars). Hashtags include #wouldyourather #shorts #science.

## pick-a-scenario (9–12 lines, ~45–60 s)
- 3 or 4 short options in one theme, e.g. "Pick a planet to stand on for 10 seconds: Venus, Mars, Jupiter, Neptune".
- Line 2: "Pick one: <theme>." Show `{"type":"options","items":["<option 1, max ~5 words>", ...]}` on that scene and the next one.
- Next scene: "Pick 1, 2, 3 or 4 and comment." with `{"type":"countdown","secs":3,"pos":[0.5,0.55]}` (at least 3.5 s).
- Then one or two lines per option revealing what would really happen. Show the options overlay with `"pick": <index>` highlighting the option being discussed, and make the 3D visual match it.
- Final reveal line: the best or surprising choice. The last line loops back into the hook. Use `{"type":"cta","text":"FOLLOW FOR MORE SCENARIOS"}` on the last scene with no options overlay there.
- Title: "Pick a <theme>… which one survives? 🤔 #shorts" style, accurate and under 100 chars. Hashtags include #pickone #shorts #science.
