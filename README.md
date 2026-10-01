# Gaze Check

Gaze Check is the webcam eye-tracking pipeline I use to collect and quality-check gaze data before running an experiment. It runs in the browser on the participant's own computer, calibrates [WebGazer](https://webgazer.cs.brown.edu/) 2.0.1, measures how far they sit from the screen, and then measures how accurate and precise the tracking actually was for that person, following the validation procedure in Brand et al. (2021). No video ever leaves the participant's computer; only the estimated gaze positions and their questionnaire answers are saved.

I wrote this README for anyone who wants to run a study with it. If you just want to see it working, skip to [Try it yourself](#try-it-yourself).

---

## What a session looks like

A session takes about five minutes. The participant moves through five stages, shown in a progress bar at the top of the page.

| Stage | What happens | Roughly |
|---|---|---|
| **1. Set up** | Participant ID, then five short screens: demographics, computer and camera, vision, measuring the screen with a bank card, and set-up tips. | 2 min |
| **2. Camera check** | A live camera preview with a checklist (face found, centred, lit, at the right distance, holding still), then a tape-measure reading of the webcam-to-eye distance. | 1 min |
| **3. Calibrate** | A dot appears in 13 places, 2 s each. The participant just watches it. Then a quick 5-point check confirms the calibration is good enough before going on. | 45 s |
| **4. Validate** | A cross appears in 12 places (a 4 × 3 grid), 2 s each, in random order. This is the measurement of data quality that goes into the results. | 30 s |
| **5. Results** | A plain-language verdict, the numbers, a map of where they looked versus where the targets were, and the data downloads. Optionally followed by a visual search task and your own experiment. | — |

At the end the participant downloads their files and emails them to you (see [Getting the data back](#getting-the-data-back)).

### Things that happen automatically

If the participant leaves the camera's view or moves more than 8 cm closer or further than where they started, the task pauses, shows them the camera, and carries on by itself once they are back. Any validation point interrupted by a pause is repeated. Pressing `Esc`, leaving full screen, or switching tabs stops the task and offers a menu to restart it.

If the quick calibration check fails, the participant is asked to recalibrate and given tips (more light, camera at eye level, sit still). After three failed checks they can choose to continue anyway, and their data is marked as not having passed.

---

## Before you run your study

### 1. Change the email address

Participants send their data to the address in `SEND_TO`, near the top of the script in `index.html`. **Change this to your own address before you send the link to anyone.** `SEND_SUBJECT` sets the subject line, which makes the emails easy to filter.

```js
const SEND_TO = 'you@your-university.edu', SEND_SUBJECT = 'eyetracking';
```

### 2. Decide how participants will open it

You have three options.

**On your own computer, for piloting:** double-click `index.html` and open it in Chrome or Edge. That's all. Other browsers may block the camera on a page opened as a file; the page tells you if that happens.

**Online, for real participants:** put the whole folder on any `https://` web server (GitHub Pages works fine). The camera only works over `https`, not plain `http`.

**On a local server**, which you only need if you host the face models yourself (step 3):

    python3 -m http.server 8000      # then open http://localhost:8000

### 3. Host the face models (recommended for real data collection)

WebGazer downloads two small face-detection models from `tfhub.dev` every time the page opens. That site now redirects to Kaggle and has had outages before, and if it is down, the tracker won't start. To remove that dependency, download the models in TF.js format and put them here:

    models/blazeface/model.json   + its group1-shard*.bin files
    models/facemesh/model.json    + its group1-shard*.bin files

They come from `https://tfhub.dev/tensorflow/tfjs-model/blazeface/1/default/1` and `https://tfhub.dev/mediapipe/tfjs-model/facemesh/1/default/1`. The page tries `./models/` first and falls back to `tfhub.dev` on its own. If you skip this step, you'll see some harmless 404 errors for `./models/...` in the browser console. Either way, the source that was actually used is recorded in the data (`face_model_source`).

This only works when the page is served (online or from a local server), not when `index.html` is opened as a file.

### 4. Give participants IDs

The first screen asks for a participant ID, which is used to label the data files. Send each participant their ID along with the link.

### 5. Tell participants what they'll need

The welcome screen tells them too, but it helps to say it in your recruitment message: a laptop or desktop with a webcam, Chrome or Edge, somewhere with good light, about five minutes (a few more if they do the search task), a bank or ID card, and ideally a tape measure or ruler.

### 6. Add your experiment (optional)

After the results, participants can go to a launcher page that links to your own task. Add it to the `EXPERIMENTS` list at the top of the script:

```js
const EXPERIMENTS = [
  { name: "My eye-tracking task", url: "https://example.org/my-task/" },
];
```

One important limitation: **the calibration does not carry over to another page.** Each experiment loads its own WebGazer and needs its own calibration. Gaze Check tells you how well webcam tracking works for this participant on this set-up; it doesn't hand a calibrated tracker to your task.

### 7. Update your ethics application and consent form

The data includes demographic and vision answers, which are personal data, plus a set of automatically collected hardware details (browser, operating system, graphics chip, camera name, screen resolution and so on). Taken together, the hardware details can come close to identifying a device, so mention them. Everything is saved only in the files the participant downloads, labelled with their participant ID; nothing is sent to a server.

---

## Viewing distance and why it matters

Accuracy and precision are reported in two units. **Pixels** come straight from WebGazer and are always reliable. **Degrees of visual angle** are what you'd normally report, but they depend on how far the participant sits from the screen, so that distance needs to be known.

The best source is a tape measure. After the camera check, participants measure from the webcam to the corner of their eye, sitting as they will for the tasks, and type it in (cm, or inches, which is the default in the US). They have to be between 50 and 70 cm; if they're not, they're asked to move and measure again. If the number they type is very different from the camera's own estimate (less than 0.55× or more than 1.8×), the page asks them to check the number and unit, since inches typed as centimetres is a common mistake, and lets them confirm it if it's right.

Participants without a tape measure can press "I don't have a tape measure". The distance is then estimated from the camera, assuming an average distance between the pupils (63 mm) and a 55° camera lens. This estimate can be off by roughly 15–25 %, and that error carries straight into the degree values (the pixel values are unaffected). These sessions are clearly flagged:

- on the results page, the degree values are marked "(estimated)";
- in the validation CSV, `distance_source` is `camera estimate`, `distance_measured_by_participant` is `no`, and `degrees_based_on` is `camera-estimated distance (approximate)`.

When you write up, report how many sessions had each kind of distance, and consider reporting degrees for the tape-measured sessions only, or for the two groups separately. If you need every session to have a measured distance, set `TAPE_SKIP_ALLOWED` to `false`.

The screen's size comes from the bank-card step: participants hold a card against the screen and resize a bar to match it. The value is remembered on that computer for next time.

---

## Getting the data back

On the final screen, participants press **Download all data** and then email the files to the address in `SEND_TO`. The page opens a pre-filled email with their ID and the list of files, but they have to attach the files themselves from their Downloads folder. It's worth checking that every participant's email actually has the attachments.

Each session produces up to three files.

**`gaze_validation_<ID>_<time>.csv`** is the one you'll use most. It has one row per validation point, followed by a block of `name,value` rows with the overall results and everything about the session.

**`gaze_raw_<ID>_<time>.csv`** has every gaze sample and event (targets appearing, pauses, resumes, clicks) with a timestamp, both raw and smoothed gaze coordinates, and the screen size on every row. Use this if you want to recompute anything yourself.

**`gaze_search_roc_<ID>_<time>.csv`** only exists if the participant did the optional visual search task.

### What's in the validation file

**Per-point rows** give the target position, the mean gaze position, accuracy and precision (combined, horizontal and vertical) in pixels and degrees, the number of valid samples, and the same accuracy and precision computed separately for the raw and smoothed gaze.

**Overall data quality:**

- `overall_accuracy_px` / `_deg`: the average distance between where they looked (mean gaze) and the target. Lower is better.
- `overall_precision_px` / `_deg`: the average RMS spread of the gaze samples around their own mean. Lower is better. Brand et al. don't say exactly how they computed RMS precision, so I'm stating my definition here for your methods section.
- `overall_accuracy_x`, `_y` and `overall_precision_x`, `_y`: the same, split into horizontal and vertical.
- `overall_accuracy_xy_mean`, `overall_precision_xy_mean`: the average of x and y, which is how Brand et al. report their overall values. Use these if you want to compare against the paper.
- `overall_raw_*` and `overall_smoothed_*`: everything above for both gaze streams. `main_results_use` says which one the main numbers are based on.
- `sampling_rate_hz`: samples per second, measured within each point.
- `valid_percent`: the percentage of frames that had a gaze estimate while a target was on screen.

**Whether the participant passed:** `calibration_check_passed` (`yes`, `no`, or `no (continued anyway)`), `calibration_check_attempts`, `calibration_check_results` (the result of each try), and `calibration_runs`.

**Session quality flags:** `fullscreen`, `viewport_changed_since_calibration`, and `position_pauses` (how many times they moved out of position).

**Distance:** `viewing_distance_cm`, `distance_source`, `distance_measured_by_participant`, `tape_step`, `tape_value`, `tape_unit`, `tape_cm`, `tape_check`, `camera_distance_estimate_cm` (the camera's estimate at the same moment, for comparison), and `camera_fov_deg_implied` (the lens angle the measurement implies).

**Settings used:** smoothing, regression, Kalman filter, calibration points and samples, the validation grid and timing, the check rule, the assumed pupil distance and camera lens angle, the face-model source, and the WebGazer version. These are there so you can check every file was collected the same way.

**Demographics** (each question can be skipped): `demo_age`, `demo_sex` (sex assigned at birth), `demo_gender`, `demo_race_ethnicity` (all that apply, separated by `;`), `demo_race_ethnicity_other`, and `demo_eye_colour`, which I ask because eye colour can affect how well tracking works. `not answered` means the question was skipped; `prefer not to say` means they chose that option. The race and ethnicity categories follow the 2024 US federal standard (OMB SPD 15). That standard is under review, and outside the US you may need different categories; you can edit them in the "Demographic questions" panel of `index.html`.

**Vision** (each question can be skipped): `vision_usual_correction`, `vision_clear_without_glasses`, `vision_wearing_now`, and `vision_screen_clear_now`. Participants are advised to take their glasses off if they can see the screen clearly without them, since reflections confuse the tracker, and to keep contact lenses in.

**Hardware** the participant reported: `device_type`, `computer_model`, `camera_type`, `webcam_model`. Browsers don't reveal the make and model of a computer, which is why I ask.

**Hardware** collected automatically: `camera` (the name the browser reports), `camera_resolution`, `camera_frame_rate`, `cameras_available`, `os`, `cpu_architecture`, `browser`, `gpu`, `cpu_cores`, `device_memory_gb` (Chrome and Edge only, capped at 8), `screen_resolution`, `device_pixel_ratio`, `touch_points`, and `user_agent`.

---

## Deciding which data to keep

The results page gives each participant a verdict based on these limits, which you can change in `GRADE`:

| | Good | Fair | Poor |
|---|---|---|---|
| Accuracy and precision (degrees) | ≤ 3° | ≤ 6° | > 6° |
| Accuracy and precision (pixels, if no distance) | ≤ 110 px | ≤ 220 px | > 220 px |

The quick calibration check before validation requires accuracy and precision within the "fair" limit, a gaze estimate on at least 80 % of frames (`PASS_MIN_VALID`), no more than one point without data, and the browser window not resized since calibration.

These are the limits I use for the on-screen feedback; they aren't a recommendation for your exclusion criteria. Decide those based on what your experiment needs (for example, how large and far apart your areas of interest are) and pre-register them if you can. The columns above give you what you need: `overall_accuracy_deg`, `overall_precision_deg`, `valid_percent`, `calibration_check_passed`, `distance_source`, and `position_pauses`.

---

## The optional visual search task

After the results, participants can do a short visual search task from Brand et al. (2021). Each round shows two normal-facing "E"s among sixteen that face other ways, and the participant clicks the two normal ones. Their clicks serve as ground truth for where they were looking, and the task scores how well fixations detected from the gaze data match those clicks, across 8 area-of-interest sizes and three minimum fixation durations (100, 150 and 275 ms). Fixations are detected with an Engbert & Kliegl (2003) velocity method. I use 25 rounds (`SEARCH_TRIALS`), about three minutes; Brand et al. used 50. The search analysis applies its own light smoothing before detecting fixations, which affects only its results, not the recorded data.

Participants can skip this and go straight to the experiment launcher.

---

## Settings

All the settings are at the top of the main script in `index.html`.

| Setting | Default | What it does |
|---|---|---|
| `SEND_TO`, `SEND_SUBJECT` | — | Where participants email their data, and the subject line |
| `EXPERIMENTS` | empty | Links shown in the experiment launcher |
| `DIST_MIN`, `DIST_MAX` | 50, 70 | Allowed webcam-to-eye distance (cm) |
| `DIST_TOL` | 8 | How far (cm) they can drift from their starting distance before a task pauses |
| `ASK_TAPE` | true | Ask for a tape-measured distance |
| `TAPE_SKIP_ALLOWED` | true | Show "I don't have a tape measure"; set false to make the measurement required |
| `VISION_REQUIRED` | false | Make the vision questions required |
| `GRADE` | see above | Limits for good / fair / poor |
| `PASS_MIN_VALID` | 80 | % of frames with a gaze estimate needed to pass the calibration check |
| `MAX_ATTEMPTS` | 3 | Failed checks before "Continue anyway" is offered |
| `CHECK_POINTS` | 5 points | Positions used in the quick calibration check |
| `SMOOTHING` | true | Whether the check and on-screen results use smoothed gaze (both are always saved) |
| `SMOOTH_ALPHA` | 0.35 | Smoothing strength (1 = none, lower = smoother) |
| `REGRESSION` | `'ridge'` | WebGazer's regression model: `'ridge'` or `'weightedRidge'` |
| `USE_KALMAN` | false | WebGazer's own Kalman filter |
| `IPD_MM` | 63 | Assumed distance between the pupils (mm), used for the camera's distance estimate |
| `CAM_FOV_DEG` | 55 | Assumed horizontal angle of the webcam's view |

`ASK_TAPE` and `SMOOTHING` also appear as switches under *Advanced options* on the last set-up screen, so they can be changed for a single session. The "Show my gaze" dot on the results page is always smoothed so it's easier to watch, whatever `SMOOTHING` is set to.

The validation timing (`DWELL` 2000 ms per target, `ITI` 250 ms blank between targets, `PRUNE` 100 ms dropped at the start of each target) follows Brand et al. (2021). `FIND_MS` (default 0) can add extra time before recording starts at each target, but that departs from the paper.

---

## How this differs from Brand et al. (2021)

If you're comparing your numbers with the paper, these are the differences to know about.

- **Validation target.** Brand et al. used small black dots on a white screen. I use a 48 px yellow cross with a shrinking ring on the same dark background as calibration. The grid positions (4 × 3, as fractions of the screen) and the timing match the paper. The order of the points is random; the paper doesn't say what order it used.
- **Screen-relative layout.** Targets are placed as fractions of the screen, so the layout looks the same on every screen. This means their distance apart in degrees varies a little with screen size and viewing distance; the file records the actual values for each session.
- **Calibration check.** I added a 5-point check after calibration so that participants with poor calibration recalibrate before validation instead of producing unusable data.
- **Search task length.** 25 rounds instead of 50.

---

## Notes for anyone comparing with data from older versions

If you collected data with an earlier version of this tool, a few things changed that affect the numbers:

- The Kalman filter was never actually on in earlier versions, even though files said `kalman_filter=on` (the call used doesn't exist in WebGazer 2.0.1). Old data was unfiltered; the column is now accurate and the default is off.
- Sampling rate is now computed within each point only. The old calculation included the gaps between points and under-reported the rate by about 15 %.
- The first 100 ms are now dropped from when the target appears, not from the first sample.
- `valid_percent` is now frames with a gaze estimate divided by all frames while a target was shown. The old value was close to 100 % by construction.
- Mouse clicks and movement before calibration no longer train the model; WebGazer's data is cleared at the start of each calibration.

---

## Try it yourself

Download the folder, double-click `index.html`, and open it in Chrome or Edge. Enter any participant ID and go through it; it takes about five minutes. You'll need a bank card, and a tape measure if you have one.

---

## Attribution and licence

This tool includes **WebGazer.js** from the Brown University HCI group, which is licensed under **GPLv3**, so this tool is distributed under **GPLv3** as well.

It uses methods from:

- Brand, J., Diamond, S. G., Thomas, N., & Gilbert-Diamond, D. (2021). Evaluating the data quality of the Gazepoint GP3 low-cost eye tracker when used independently by study participants. *Behavior Research Methods*, 53(4), 1502–1514. The validation grid and timing, and the visual search task and its analysis.
- Li, Q., Joo, S. J., Yeatman, J. D., & Reinecke, K. (2020). Controlling for participants' viewing distance in large-scale, psychophysical online experiments using a virtual chinrest. *Scientific Reports*, 10, 904. Only the bank-card step for measuring the screen; their blind-spot test for viewing distance isn't used.
- Engbert, R., & Kliegl, R. (2003). Microsaccades uncover the orientation of covert attention. *Vision Research*, 43(9), 1035–1045. The fixation detection in the search task.
