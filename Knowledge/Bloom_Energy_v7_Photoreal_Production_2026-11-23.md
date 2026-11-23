# Bloom Energy — v7 photographic realism direction / source and QA

Date: 2026-11-23

## Binding user feedback
- **«Все должны выглядеть максимально реалистично, не выглядеть ИИ-генерацией»**.
- User also specifically rejected visual **«червячки» / glowing squiggles** over static images. They want more narrative object/camera motion, many different shots and viewing angles, main Russian text centered.
- Film remains SILENT, 47s, six approved acts, exact ending **«КОСМОС БЛИЖЕ, ЧЕМ ВАМ КАЖЕТСЯ»**.

## Production changes from v6 → v7
1. Removed hand-drawn 3D box/cabinet primitives, pseudo-Mars model and floating decorative energy snakes. Instead use photographic-looking scene plates, restrained naturalistic camera pushes/pans and 18 editorial shots in 47s.
2. Fixed premature display of Oracle signage in pre-Oracle 'grid bottleneck' scene. The dramatic blackout remains metaphor, not real Oracle incident.
3. Scene 3 stays grounded: exterior fuel-cell equipment, natural gas and air converting electrochemically to electricity. Don't masquerade a fake X-ray as manufacturer-approved CAD; plant interiors require validated factory assets.
4. The photographed-looking plant shots are **generated concept plates**, NOT documentary camera footage of Oracle/Bloom; they cannot be labeled 'real footage'. This is an internal visual concept cut, not clearance-ready advertising footage.
5. Large central captions without opaque black rectangular cards, restrained neutral color grade and minimal film grain. Keep verified numerical overlays separate from generated imagery.
6. Financial graphics use only factual Q3 2025 vs Q3 2026 figures: revenue $519m to $1,236m (+138.1% YoY), GAAP net income attributable to common stockholders ~$250.3m. S&P 500 inclusion Sep 21 2026. No fabricated share-price time series.
7. Master remains 16:9 1280x720 at 24fps; no audio track. Vertical 9:16 would need recut.

## Official photographic and video source strategy for real-world standard
- Bloom official [Press Kit](https://www.bloomenergy.com/press-kit/) exposes photos, videos and a logo package and press contact **press@bloomenergy.com**. Check actual reuse permissions before using in distributable public film. Access to a press kit alone is not blanket license.
- Bloom [Installation Video](https://www.bloomenergy.com/resource/bloom-energy-installation-video/) shows authentic fabrication/installation and fuel cells.
- Bloom official [Installation Process: From Site Prep to Full Power](https://www.youtube.com/watch?v=OagjMeIzlU8), published June 2026.
- Bloom [Energy Server Technology](https://www.bloomenergy.com/technology/) explains and photographs fuel cell→stack→module→server geometry.
- NASA JPL Mars photos in NASA archive, including [Global Color Views of Mars](https://www.jpl.nasa.gov/images/pia00407-global-color-views-of-mars/), for a real planetary first shot. Follow NASA media-use rules, credit source and do not imply Bloom was deployed on Mars.
- For Oracle real site video: a Bloom press release only verifies an Oracle collaboration and 55-day delivery, not a rights-cleared actual camera take. If authentic assets unavailable, label illustrative generic campus footage (do NOT imply a particular facility).

## Runtime and scene staging
| Act | Time | What a newcomer must understand |
|---|---|---|
| 1 NASA/Mars | 00–07 | Bloom's roots in NASA Mars research (oxygen/fuel research, not deployed on Mars) |
| 2 Data-centre electricity | 07–15 | Data-centre energy use may roughly double by 2030; IEA scenario not actual 2030 |
| 3 Fuel cells | 15–23 | Natural gas + air → electricity via SOFC, onsite, CO2 remains |
| 4 Oracle | 23–31 | The 55-day operational system is a documented company-reported case; **up to** 2.8GW is a wider agreement potential |
| 5 Finance | 31–39 | +138.1% YoY sales; GAAP Q3 net profit ~$250.3m |
| 6 Index & cosmos | 39–47 | S&P 500 admission then only «КОСМОС БЛИЖЕ, ЧЕМ ВАМ КАЖЕТСЯ» |

## Local artifact targets (not GitHub binary uploads)
- `/mnt/data/Bloom_Energy_REALISM_v7_47s_SILENT.mp4`
- `/mnt/data/Bloom_Energy_REALISM_v7_18_SHOTS.jpg`
- `/mnt/data/render_bloom_v7_realism.py`

## Honesty and QC gates
- Clip is a **photoreal-styled 2.5D editorial prototype** built from original concept images, not real on-location footage, not full physical 3D, and not LTX GPU-generated motion. This limitation must be disclosed.
- Reject fabricated logos/plant topology, any false claim of actual Oracle blackout and unsupported visuals of manufacturing internals.
- Final public edition should replace concept plates with cleared corporate footage, NASA imagery and genuinely verified product CAD if used.
- Verify exactly 47.000s, single H.264 stream at 24fps, no audio stream, readable titles and that closing line is exact.
- AICS source/data/model unaffected.
