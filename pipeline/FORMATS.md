# Hypotheticool Short formats

Every Short is one of three formats. Store the format in the topic JSON as `"format": "what-if" | "would-you-rather" | "pick-a-scenario"`. Older topic files with no `format` field count as `what-if`.

## Rotation (Shorts only; the weekly long video is always What If)
Repeat this 4-step cycle: **what-if → would-you-rather → what-if → pick-a-scenario**.
To find the next format, sort the Short topic files in `pipeline/topics/` and the claims in `pipeline/claims/` by post date/time and take the latest one that has a format (a claim file's first line can start with `format: <name>`). Then use the next step of the cycle. If two runs collide on the same slot, the claim file decides.

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
