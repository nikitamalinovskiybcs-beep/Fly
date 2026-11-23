# Bloom Energy — cinematic production reboot v9
Date: 2026-11-24
Status: **research + production specification only, NOT an MP4**.
Source: compare original 24-second Mars/SOFC first concept with v8 Telegram 47-second output.

## Diagnosis, 0/10 audience verdict
v8 failed because visual language switched from the early concept's cinematic amber Mars / coherent dark-blue AI world to narrow static photographic crops inside large black margins. Most of the visible action was a changing caption, unmotivated camera crop or a screen overlay. The viewer did not see believable physical motion, events or camera-body relationships. More animated text is not the solution.

## Research, verified GitHub projects
1. [LTX-2.5 source](https://github.com/Lightricks/LTX-2). Genuine video diffusion text-to-video and image-to-video; full local quickstart ~66 GiB weights, substantial CUDA GPU required. Current sandbox has no NVIDIA GPU, so **not used**.
2. [ComfyUI LTX-2.5 workflows](https://github.com/Lightricks/ComfyUI-LTXVideo/tree/master/example_workflows/2.5): `LTX-2.5_T2V_I2V_Two_Stage_Distilled.json` for first frame to dynamic video, `LTX-2.5_ICLoRA_Motion_Track_Distilled.json` for sparse motion tracks, `LTX-2.5_ICLoRA_Union_Control_Distilled.json` to guide shots with reference video depth/Canny.
3. [Wan 2.2 Camera Control docs](https://github.com/Comfy-Org/docs/blob/main/tutorials/video/wan/wan2-2-fun-camera.mdx) for controlled virtual camera motion.
4. [givemotion](https://github.com/givemotion/givemotion) for HTML/CSS-based motion design / exact captions and chart components **only after** true moving video has been generated. Not a substitute for moving physical subjects.
5. [Runway image-to-video prompting guide](https://help.runwayml.com/hc/en-us/articles/48324313115155-Image-to-Video-Prompting-Guide) and [Gen-4.5](https://help.runwayml.com/hc/en-us/articles/46974685288467-Creating-with-Gen-4-5) — commercial video generation alternative; plugin has been suggested but **not yet connected**. Actual shot generation remains blocked on connection.

## Locked visual rules
- Telegram 9:16, target 1080×1920, 24 fps, 47 secs, **strictly no audio**.
- Return to early dramatic coherent cinematography: warm Mars origin → blue server tech → realistic stainless fuel-cell plant → Oracle corporate architecture → precise financial performance → physical NYSE LED board → the orbit scene.
- **14 planned moving shots**, NOT 7 static cards. Each shot contains a real moving subject (wheel turning/dust, server fans/rack parallax, crane operating, pipes/fans, plant commissioning, moving LED pixels or orbital geography).
- Absolutely no random glowing ribbons/worms, AI-created fake typography or corporate logos, synthetic stock-price candles, physically implausible equipment or permanently floating UI panes.
- One camera move per shot with beginning/middle/end; do not merely zoom or pan a still. Use editorial match cuts and depth/occlusion.
- Make all Russian text in a deterministic post pass, large, centered and with safe margins. Film first, text second. One meaningful on-screen takeaway at a time.
- Periodically inspect at phone screen size; reject any shot with warped industrial geometry or subjects that remain static.
- All artistic re-creations must be distinguished from real NASA / Oracle / NYSE archival footage. Do not imply a real Oracle blackout.
- Ending last displayed words exactly: **КОСМОС БЛИЖЕ, ЧЕМ ВАМ КАЖЕТСЯ**.

## 14-shot timeline / editor acceptance
| Shot | Time, seconds | Physical movement, camera | Text in post |
|---|---:|---|---|
| 01 Mars orbit | 0–3.1 | Massive planet rotates slowly, camera executes orbital dolly/tilt | КОСМОС |
| 02 Rover | 3.1–6.7 | Rover drives, wheel rotates, dust shifts, camera follows | ОТ ИССЛЕДОВАНИЙ NASA |
| 03 Server corridor | 6.7–10.1 | Camera physically flies between server racks; fans spin | ИИ НУЖНО ЭЛЕКТРИЧЕСТВО |
| 04 AI campus | 10.1–13.7 | Crane lowers equipment; camera rises to reveal campus | ЭЛЕКТРОСЕТИ НЕ УСПЕВАЮТ |
| 05 Bloom cabinets | 13.7–17.5 | Lateral tracking through fuel-cell exterior, real parallax | BLOOM ENERGY |
| 06 SOFC close-up | 17.5–21.7 | Equipment rack focus, fans and exhaust physically move | ЭНЕРГИЯ ПРЯМО НА ПЛОЩАДКЕ |
| 07 Oracle building | 21.7–25.0 | Camera traverses real-looking glass campus | ORACLE × BLOOM |
| 08 Installation | 25.0–28.7 | Physical time-lapse of cabinet placement, no shape-morph | 55 ДНЕЙ |
| 09 Operating system | 28.7–32.0 | Ventilation turns and real building lights come up | ЗАПУСК ДЛЯ ORACLE |
| 10 Q3 revenue | 32.0–35.0 | Two real proportional 3D glass monoliths, one grows | ВЫРУЧКА +138,1% |
| 11 Profit | 35.0–38.3 | Camera passes through revenue object to clean dark panel | ЧИСТАЯ ПРИБЫЛЬ $250,3 МЛН |
| 12 Stock exchange | 38.3–41.3 | Physical camera cranes past LED ticker, exact lettering in post | BLOOM ENERGY В S&P 500 |
| 13 Earth rise | 41.3–43.6 | Earth limb shifts under retreating orbital camera | none |
| 14 Cosmic ending | 43.6–47.0 | Earth/Mars subtly drift; 2.7s title hold, fade last 0.5s | КОСМОС БЛИЖЕ, ЧЕМ ВАМ КАЖЕТСЯ |

## Guardrails for financial and technical accuracy
- NASA precursors investigated Mars oxygen and fuel. No Bloom Energy hardware actually on Mars.
- SOFC natural gas may generate CO2 despite no combustion in electrochemical cell.
- Oracle 2025 installation in 55 days is one reported deployment. "Up to 2.8 GW" is a future agreement scale, NOT already installed.
- Q3 2026 revenue +138.1% YoY; net income figure to common shareholders $250.3m, not operating income.
- Bloom inclusion in S&P 500 effective 2026-09-21. Electronic facade illustrative, not footage of an actual ceremony.
- Claims per source: https://spinoff.nasa.gov/node/10637 ; https://www.bloomenergy.com/news/bloom-energy-and-oracle-expand-strategic-partnership-to-deploy-up-to-2-8-gw-to-accelerate-ai-infrastructure-build-out/ ; https://www.bloomenergy.com/news/bloom-energy-reports-record-third-quarter-2026-financial-results-and-raises-full-year-2026-guidance/ ; https://press.spglobal.com/2026-09-04-Bloom-Energy,-Illumina,-and-Everpure-Set-to-Join-S-P-500-Others-to-Join-S-P-100,-S-P-MidCap-400,-and-S-P-SmallCap-600 .

## Build status
- [x] Compared first and last renders, diagnosed failure.
- [x] Reviewed original official video-engine GitHub documentation.
- [x] Wrote complete 14-shot model-specific prompts and production notes, plus local JSON/ZIP package.
- [ ] Connected Runway or CUDA video model.
- [ ] Generated actual moving 14 clips.
- [ ] Rendered final cinematic v9 MP4.
- [ ] Passed visual quality gate on all shots.

**Do not label next output 'blockbuster' or 'final' unless the real-motion gate passes.**
AICS repo code, data and trading model unchanged.