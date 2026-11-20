# Hypotheticool Short formats

Every Short is one of three formats. Store the format in the topic JSON as `"format": "what-if" | "would-you-rather" | "pick-a-scenario"`. Older topic files with no `format` field count as `what-if`.

## Rotation (Shorts only; the weekly long video is always What If)
Repeat this 4-step cycle: **what-if → would-you-rather → what-if → pick-a-scenario**.
Special posts (claim/topic format starting with `special-`, e.g. a trending-event special the user asked for) are SKIPPED when working out the rotation. To find the next format, sort the Short topic files in `pipeline/topics/` and the claims in `pipeline/claims/` by post date/time and take the latest one that has a format (a claim file's first line can start with `format: <name>`). Then use the next step of the cycle. If two runs collide on the same slot, the claim file decides.

## The first second (ALL Shorts): stop the swipe
Our first Short kept only 54% of viewers (46% swiped away immediately). Top Shorts keep 70%+. Every Short must win the first second:
- **Frame 1 is the payoff.** The most dramatic, high-contrast shot of the video is already in motion on the very first frame: the subject is big in frame, bright against the dark, with something visibly happening (exploding, falling, collapsing, glowing). No black or empty frames, no fade-in, no intro, no logo, no slow establishing shot.
- **The voice starts on frame 1.** audio_prep/engine do this automatically (HOOK_LEAD = 0.02 s for line 1); never add silence or music before it. Line 1 is at most ~2 seconds when spoken (under 8 words).
- **On-screen hook text from frame 1:** scene 0's meta.json must include `{"type":"hook","text":"<2-6 punchy words>"}`, a short, bold, TRUE version of the payoff (e.g. "THE SKY WOULD GO DARK", "2 TONS WOULD SURVIVE"). It's drawn big at the top (white, last row yellow) and is visible from frame 1, so people who scroll with the sound off are hooked too. Keep the line-1 caption too.
- **Create a question in the viewer's head within 2 seconds** (stakes, surprise, a number, "you"), then answer it by the end, so they stay to the loop.
- In market research, study the first second of the top Shorts you find (what's on screen, the first words) and use the patterns that work, in our own words and visuals.
- When analytics are available (Metricool, or numbers the user shares), log each Short's "viewed vs swiped away" and average % viewed in the research log, and adjust hooks based on what keeps people.

## Market research: do this BEFORE choosing any topic (Shorts and the long video)
The goal is to pick topics that are already proven to pull views, then make our own accurate, original 3D version. Spend about 15–25 minutes on this and use many searches.
1. **What's working in this format right now.** Use WebSearch/WebFetch to find the most-viewed recent Shorts and videos for the chosen format, e.g. "what if" science shorts, "would you rather" space/science, and "pick a planet/scenario" shorts. Check YouTube search results, the Shorts tabs of the top channels in each niche, and pages that list viral Shorts. Note titles, view counts, upload age (views per day matters more than totals), hooks and thumbnails. Look for topics and angles that keep repeating among the big hits.
2. **What people are searching and talking about.** Check Google Trends and trending-topic pages, this week's science and space news, and popular threads on Reddit (r/space, r/askscience, r/whatif, r/WouldYouRather, r/nostupidquestions) and similar communities. Prefer a topic with rising interest.
3. **Our own results.** Use Metricool analytics (getAnalyticsAvailableMetrics + getAnalyticsDataByMetrics, blogId 8192121, YouTube) to see which of our posts got the most views, watch time, likes and comments. Do more of what works for us (themes, formats, title styles) and less of what flopped.
4. **Pick.** Choose the topic with the best mix of proven demand + rising interest + fit for our channel (science, showable in 3D, 100% verifiable). Never copy another creator's script, title or visuals; only use the idea as a starting point.
5. **Log it.** Write pipeline/research/<post-date>-<slug>.md with: the format, the 5–10 best examples you found (title, channel, views, age, URL), trend signals, our own analytics takeaways, the 2–3 runner-up ideas, and why you picked this one. Commit it with the video. Later runs read the latest 3–5 logs first so research builds over time (reuse good runner-up ideas that aren't taken yet).

## Visual accuracy and detail (EVERY video, EVERY topic)
Space, Earth science, the human body, oceans, weather, animals, physics, engineering, history: all of them get the same standard. Graphics must be as detailed, precise and accurate as the narration. Nothing generic, nothing invented, nothing low-effort.

**1. Real data first.** If a real dataset or official model exists for the subject, use it:
- Space: `kit.earth()` (real 8K Blue Marble-based map, night lights, clouds, ocean glint; `face_lon` turns the region being discussed toward the camera, e.g. -80 Americas, 15 Europe/Africa, 100 Asia), `kit.moon()`, `kit.planet(...)` (real maps and tilts, Saturn's real rings), `kit.sun_sphere()`, `kit.world()` (real Milky Way), and `kit.nasa_model('<name>')` (official NASA spacecraft; catalog in assets/nasa_models.txt; `kit.hubble()` uses it).
- Human body: `kit.anatomy('<regex>', ...)` loads real segmented human anatomy (BodyParts3D: 900+ organs, bones, vessels, muscles, brain regions; catalog in assets/anatomy_parts.txt), at true proportions with realistic tissue colors and subsurface scattering. Example: `kit.anatomy('wall of heart', 'aorta', 'lobe of .* lung', size=3)`. Never sketch organs by hand when the real part exists.
- Anything else: search GitHub for an openly licensed 3D model or dataset of the exact subject (e.g. `gh api "search/repositories?q=<subject>+glb"` or `search/code?q=<subject>+extension:glb`). Use it only if its license is CC0, public domain, CC BY or CC BY-SA, or MIT (check the LICENSE file) and it looks like the real thing. Download it into /home/claude/nasa_cache, import it (glb via `nasa_model`-style import, STL/OBJ via bpy.ops.wm.stl_import/obj_import), and add its credit to the post (see CREDITS.md). Note the source in the research log.

**2. Physically based everything else.** When there's no ready model, build one in kit.py (reusable) to the standard of the real-data assets:
- Lighting: `kit.sky(sun_elevation, sun_rotation)` gives physically based daylight (real atmospheric scattering, sunrise/sunset colors) with a matching sun. Space shots use `kit.world()` and one sun. Light direction stays consistent between shots.
- Materials: `kit.mat_pbr(kind)` has real optical values (skin/organ/muscle with subsurface scattering, bone, blood, glass IOR 1.5, diamond 2.42, ice 1.31, water 1.333, gold/silver/copper/iron/steel/aluminium, rust, concrete, wood, fur, feathers, leaves, bark, sand, rock, snow, lava, magma). `kit.mat_water()` absorbs light with depth like real water.
- Nature: `kit.ocean()` is a spectral wave simulation with real wave shapes and wind-driven whitecaps. `kit.terrain(kind=...)` gives detailed landscapes (rock, desert, snow, grass, lava, volcanic, ice, mud). `kit.volume_cloud(kind=...)` makes real volumetric clouds, storm cells, smoke, volcanic ash, fog, steam and dust.
- Modeling: match real reference photos (look up at least 2 photos or diagrams of the exact subject from reputable sources before modeling). Get the proportions right from real measurements, use enough geometry (subdivision, bevels, no faceting), and add surface detail (bump/normal noise, wear, texture variation) and secondary details (seams, bolts, veins, scales, feathers, pores) where they would be visible.

**3. Precision on screen.**
- Sizes, distances, speeds and quantities are true to scale or labeled "not to scale". `kit.scale_ref(1.8)` adds the astronaut at real human height for size comparisons.
- Real colors (e.g. Mars rust-orange, deoxygenated blood is dark red not blue, real animal coloration). Correct counts (legs, planets, chambers of the heart, bones). Correct orientation and placement (left/right organs, north up, real geography).
- Processes are shown as they really happen (e.g. how a tornado forms, how a tsunami's wave grows near shore, how blood flows through the heart), matching the cited sources.
- Any on-screen number, label, chart or map uses the sourced value.

**4. Detail and polish.** The subject fills the frame. Use macro-style depth of field for small subjects and slow realistic motion (rotation, drift, flow, breathing, waves). Keep the channel style on top: cinematic lighting, warm glows, the white astronaut mascot as the "you" in the story.

**5. Check before the full render.** Render a still of every scene and compare it side by side with real reference imagery (NASA/ESA/NOAA/USGS photos, medical atlases, wildlife photos). Fix anything inaccurate, generic, faceted, blurry, flat-lit or out of scale. Note the reference URLs used for each scene in the research log.

**Credits:** the post text must end with the credit line(s) in pipeline/assets/CREDITS.md for the assets actually used (attribution is required for CC BY / CC BY-SA assets).
**Setup:** `pip install --break-system-packages DracoPy pygltflib` is required (NASA models are Draco-compressed and kit decodes them once). Models and anatomy parts download on demand to /home/claude/nasa_cache.

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
