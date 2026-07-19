# Public Dataset Demo

## Dataset

- Title: `Aerospace Ground Equipment ensures aircraft are ready for flight`
- Publisher: DVIDS / U.S. Air Force
- Author credit on DVIDS: Senior Airman Daira Jackson / 386th Air Expeditionary Wing
- Official source: https://www.dvidshub.net/video/838428/aerospace-ground-equipment-ensures-aircraft-ready-flight
- Copyright and public-use terms: https://www.dvidshub.net/about/copyright
- Dataset identifiers: Video ID `838428`, VIRIN `220405-F-FU631-2001`, filename `DOD_108909050`
- Date taken: `2022-04-05`
- Date posted: `2022-04-11`
- Download date for this integration: `2026-07-19`

DVIDS marks the source video as public domain and says the work must comply with the restrictions on its copyright/public-use page. That page explains that U.S. Government visual information generally is not eligible for U.S. copyright protection when created by government employees as part of official duties, while also preserving publicity, privacy, trademark, and non-endorsement limitations. The appearance of U.S. Department of Defense visual information does not imply or constitute DoD endorsement.

## Why This Dataset

AeroRamp Vision accepts uploaded video and runs computer-vision tracking, alert review, evidence capture, turnaround timelines, and operational dashboards. This DVIDS video shows real aerospace ground equipment maintenance at an air base, so it is closer to the ramp-operations domain than a generic object-detection image set while remaining publicly accessible and legally documented.

The clip is used only for public demo inference with the CPU `motion` detector. It is not used for model training, site validation, airport certification, safety certification, or accuracy benchmarking.

## Files

```text
sample-data/dvids-age-public.mp4
sample-data/dvids-age-public.json
data/NOTICE.md
scripts/download_public_dataset.py
```

The committed MP4 is a small processed derivative. Raw source media and any larger local downloads belong under `data/public/` or `data/raw/`, both of which are Git-ignored.

## Reproduction

```bash
py -3.12 scripts/download_public_dataset.py --force
```

Default preparation settings:

- Source stream: official DVIDS/CloudFront 768x432 HLS rendition.
- Start: 8.0 seconds into the source video.
- Duration: 36.0 seconds.
- Output: 640 pixels wide, original aspect ratio, 12 fps MP4.
- Manifest: `sample-data/dvids-age-public.json`.

If local OpenCV/FFmpeg cannot read HLS streams, use the official full MP4 fallback:

```bash
py -3.12 scripts/download_public_dataset.py --force --source-url https://d34w7g4gy10iej.cloudfront.net/video/2204/DOD_108909050/DOD_108909050.mp4
```

## Fields Used

AeroRamp Vision uses video frames, frame dimensions, frame rate, duration, and derived frame timestamps. The project does not use DVIDS account data, comments, analytics counters, or any manually authored labels from the source page.

## Transformations

- Selected a short window from the official public video stream.
- Resampled to 12 fps for CPU-friendly local development.
- Resized to 640x360 for small repository size and repeatable screenshots.
- Stored a JSON manifest with source, license, transformation, frame-count, and SHA-256 metadata.
- Ran the normal upload and `motion` detector workflow to create tracks, review candidates, snapshots, annotated evidence clips, dashboard records, and reports.

No detections, bounding boxes, alerts, screenshots, or metrics were manually drawn or edited.

## Limitations

- The default motion detector emits generic `moving_object` tracks. It does not classify aircraft, people, jammers, generators, or other aerospace ground equipment.
- The video is from one public B-roll source and is not representative of all airports, camera views, lighting, weather, safety procedures, or operating environments.
- People may appear in the public source video. The repository uses a short public-domain demo derivative and does not include private airport footage, passenger data, credentials, or customer data.
- Motion-triggered safety candidates require human review and are decision-support records only.
- No training or ground-truth accuracy evaluation is performed from this dataset.

## Removal

To remove locally prepared dataset files:

```bash
del sample-data\dvids-age-public.mp4
del sample-data\dvids-age-public.json
rmdir /s /q data\public
```
