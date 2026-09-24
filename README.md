# Gaze Check - webcam eye-tracking calibration & validation

A single-page, browser-based tool that calibrates a webcam eye tracker (WebGazer),
estimates viewing distance, and validates data quality (accuracy, precision, sampling
rate) following the procedure of Brand et al. (2021). It runs entirely in the browser;
no video leaves the device - only gaze coordinates are recorded.

Everything is done with **WebGazer 2.0.1**. Viewing distance comes from the
participant's tape measurement, or the camera's estimate if they have no tape measure; no
other face-tracking library is loaded.

## Use it

**Quickest:** double-click `index.html` so it opens in **Chrome or Edge**. That's all.
(Other browsers may refuse the camera on a page opened as a file; the page says so if
that happens.) On a file page the face models always download from `tfhub.dev`, because
browsers can't read the local `models/` folder from a file page.

**For real participants online:** put the folder on an `https://` web server.

**Local server** (needed only if you host the face models in `models/`):

    python3 -m http.server 8000      # then open http://localhost:8000

The participant is guided through five steps, shown in the bar at the top:

1. **Set up** - participant ID; demographic questions; computer type, computer model,
   and camera (built-in or separate, and its model); vision questions (glasses, contact
   lenses, and whether they can see the screen clearly with and without glasses);
   screen size with a bank card; set-up tips; full-screen
   option. The computer and screen answers are remembered on that computer.
2. **Camera check** - live preview with a checklist (face found, centred, lighting,
   distance, holding still), then the webcam-to-eye distance measured with a tape
   measure (see below). Continue unlocks when everything is green.
3. **Calibrate** - 3-2-1 countdown, then follow the dot.
4. **Validate** - as in Brand et al. (2021): 12 black dots, 0.44° of visual angle across,
   shown one at a time on a white screen for 2000 ms each, with a 250 ms blank screen
   between dots. The dot simply appears (no animation), and nothing else is on screen
   while dots are shown. The first 100 ms after each dot appears are dropped before
   accuracy and precision are computed. Dot size and positions are both fractions of the
   screen, so the layout looks the same on every screen: the dot is 1.27% of the screen
   width across, which is Brand's 0.44° on their laptop (1366 × 768; screen size not
   reported, but their numbers point to 15.6 inches) at 57 cm.
5. **Results** - a plain-language verdict, the numbers, a map of the points, and the
   downloads. Then optionally the visual search task or an experiment.

If the participant leaves the camera's view or moves more than 8 cm from where they
started, the task pauses, shows the camera, and carries on by itself once they are back.
Validation points interrupted by a pause are repeated. `Esc`, leaving full screen, or
switching tabs stops the task and offers a restart menu.

## Settings

At the top of the main script in `index.html`:

| Setting | Default | Meaning |
|---|---|---|
| `EXPERIMENTS` | - | Links shown in the experiment launcher |
| `IPD_MM` | 63 | Assumed distance between the pupils (mm), the ruler for viewing distance |
| `CAM_FOV_DEG` | 55 | Assumed horizontal field of view of the webcam |
| `ASK_TAPE` | true | Ask participants to measure the webcam-to-eye distance with a tape measure |
| `TAPE_SKIP_ALLOWED` | true | Show "I don't have a tape measure"; set false to make the measurement required |
| `VISION_REQUIRED` | false | Set true to make the vision questions required (by default every question can be skipped) |
| `SMOOTHING` | true | Moving-average gaze smoothing (off = WebGazer's raw output is recorded) |
| `SMOOTH_ALPHA` | 0.35 | Smoothing strength when on (1 = none, lower = smoother) |
| `USE_KALMAN` | false | WebGazer's Kalman filter (see note below) |
| `REGRESSION` | `'ridge'` | `'ridge'` or `'weightedRidge'` |
| `DIST_TOL` | 8 | cm of drift before a task pauses |
| `GRADE` | see file | Good / fair limits for the verdict |

`ASK_TAPE` and `SMOOTHING` set the defaults of the two switches under *Advanced
options* on the set-up screen, so they can also be changed per session. The on-screen
"Show my gaze" dot is always smoothed for display; what is recorded follows
`SMOOTHING`. The validation timing (`DWELL` 2000 ms, `ITI` 250 ms, `PRUNE` 100 ms) follows Brand et
al. (2021). `FIND_MS` (default 0) can add extra time before recording starts, but that
departs from the paper. The search-task analysis keeps its own 3-sample smoothing before fixation
detection; that only affects the ROC numbers, not the recorded data.

## Viewing distance: tape measure

Results are reported in pixels and degrees. Pixels come straight from WebGazer; degrees
need the viewing distance. The welcome screen tells participants they'll need a bank or
ID card and, if they have one, a tape measure or ruler. After the camera checklist they
measure from the webcam to the corner of their eye, sitting as they will during the
tasks, and type it in (cm or inches; inches is the default for US locales).

Participants without a tape measure can press "I don't have a tape measure". The camera
estimate is then used instead. It assumes an average face and a 55° lens and can be off
by roughly 15-25 %, which carries straight into the degree values (the pixel values are
not affected). **These sessions are flagged:**

- on the results page, the degree value is marked "(estimated)" and a note explains why;
- in the validation CSV, `distance_source` = `camera estimate`,
  `distance_measured_by_participant` = `no`, `tape_step` = `skipped (no tape measure)`,
  and `degrees_based_on` = `camera-estimated distance (approximate)`.

In your report, give the number of sessions of each kind, and consider reporting degrees
for the tape-measured sessions only, or the two groups separately. Set
`TAPE_SKIP_ALLOWED` to false if every session must have a measured distance.

If the typed value is very different from the camera estimate (less than 0.55x or more
than 1.8x), the page asks them to check the number and unit (e.g. inches typed as cm)
and lets them confirm it anyway. When they press Continue, the camera's eye-gap reading
at that moment is scaled to their measurement, so the "you moved" pauses and live
distance during the tasks are in their measured centimetres.

## Face-model files (recommended)

WebGazer 2.0.1 downloads two small face models from `tfhub.dev` every time the page
opens. `tfhub.dev` now redirects to Kaggle and has had outages and CORS problems in
the past, which would stop the tracker from starting. To avoid depending on it, host
copies yourself:

    models/blazeface/model.json   + its group1-shard*.bin files
    models/facemesh/model.json    + its group1-shard*.bin files

(TF.js format, from `https://tfhub.dev/tensorflow/tfjs-model/blazeface/1/default/1`
and `https://tfhub.dev/mediapipe/tfjs-model/facemesh/1/default/1`).
The page tries `./models/` first and falls back to `tfhub.dev` automatically. Without
the folder you will see harmless 404s for `./models/...` in the browser console. The
source actually used is written to the validation CSV (`face_model_source`), and the
welcome screen shows an error if the models cannot be loaded.

## Output files

- `gaze_validation_<ID>_<time>.csv` - one row per validation point, then summary
  metrics, all in pixels and degrees:
  - **Combined** (as before): `accuracy` = distance between the mean gaze position and
    the target; `precision` = RMS spread of the samples around their mean.
  - **Horizontal and vertical**, per point and overall: `accuracy_x` / `accuracy_y` =
    horizontal / vertical distance between the mean gaze position and the target;
    `precision_x` / `precision_y` = RMS spread around the mean in that direction.
  - **Averaged over x and y** (`overall_accuracy_xy_mean`, `overall_precision_xy_mean`),
    the way Brand et al. (2021) report their overall values. Their paper doesn't say
    exactly how its RMS precision was computed; the definition above (spread around
    the mean) is stated here so your report can say which one you used.
  - **Set-up details:** screen size, full screen, pauses, calibration runs, smoothing,
    model source, WebGazer version, assumptions used.
  - **Distance:** `distance_source` (tape measure / camera estimate),
    `distance_measured_by_participant` (yes / no), `tape_step` (measured / skipped (no tape measure) /
    not reached / off), `degrees_based_on` (tape-measured distance / camera-estimated
    distance (approximate)), `tape_value`, `tape_unit`, `tape_cm`, `tape_check` (ok, or
    confirmed after differing from the camera estimate), `camera_distance_estimate_cm`
    (the camera's own estimate at the same moment, for comparison), and
    `camera_fov_deg_implied` (the lens angle the measurement implies).
  - **Validation targets:** `validation_target`, `validation_target_fraction_of_width`,
    `validation_target_px`, `validation_target_deg` (actual size for this session),
    `validation_grid_x_fractions`, `validation_grid_y_fractions`, `validation_target_ms`,
    `validation_blank_ms`, `validation_pruned_ms`, `validation_extra_find_ms`.
  - **Demographics (optional; each question can be skipped):** `demo_age` (years),
    `demo_sex` (sex assigned at birth: female / male / intersex), `demo_gender` (woman /
    man / non-binary / self-described: ...), `demo_race_ethnicity` (all that apply,
    separated by `;`), `demo_race_ethnicity_other` (their own description), and
    `demo_eye_colour` (brown / hazel / green / blue / grey / other). Eye colour is asked
    because it can affect how well eye tracking works. In every demographic and vision
    column, `not answered` means the question was skipped and `prefer not to say` means
    the participant chose that option.
  - **Race and ethnicity categories** follow the 2024 US federal standard (OMB SPD 15):
    one combined question, select all that apply, with the seven minimum categories.
    That standard is under review, and outside the US you may need local categories;
    edit the list in the "Demographic questions" panel of `index.html`.
  - **Vision (optional; each question can be skipped):**
    `vision_usual_correction` (none / glasses / contact lenses / glasses and contact
    lenses), `vision_clear_without_glasses` (yes / no / n/a),
    `vision_wearing_now` (none / glasses / contact lenses), and
    `vision_screen_clear_now` (yes / no). Participants are advised to take glasses off
    if they can see the screen clearly without them, to keep them on if they can't, and
    that contact lenses are fine. If they say they can't see the screen clearly, the
    results page notes it.
  - **Hardware (participant's answers):** `device_type`, `computer_model`, `camera_type`
    (built-in / separate), `webcam_model`.
  - **Hardware (automatic):** `camera` (the name the browser reports, e.g. "FaceTime HD
    Camera" or "Logitech Webcam C920"), `camera_resolution`, `camera_frame_rate`,
    `cameras_available`, `os`, `cpu_architecture`, `browser`, `gpu` (often identifies
    the laptop's chip, e.g. "Apple M2" or "Intel Iris Xe"), `cpu_cores`,
    `device_memory_gb` (Chrome/Edge only, capped at 8), `screen_resolution`,
    `device_pixel_ratio`, `touch_points`, `user_agent`.
- `gaze_raw_<ID>_<time>.csv` - every gaze sample and event (targets, pauses, resumes,
  clicks) with the same header as before, and the screen size on every row.
- `gaze_search_roc_<ID>_<time>.csv` - visual search task results (25 rounds by
  default, `SEARCH_TRIALS`; Brand et al. used 50).

Browsers don't reveal the computer's make and model, which is why the participant is
asked. The camera name only appears after camera permission is granted. Taken together,
the automatic hardware details can come close to identifying a device, so mention them
in your consent form / ethics application. The same goes for the demographic and vision answers,
which are personal data; they are saved only in the downloaded files, with the participant ID.

### Changes that affect comparison with older data

- **Validation targets** follow Brand et al.: black dots on white, with the paper's
  timing, sized and placed as fractions of the screen (see step 4). Because the layout
  scales with the screen, the dot's size in degrees varies a little with screen size and
  viewing distance; the CSV records the actual size for each session
  (`validation_target_px`, `validation_target_deg`). Two details the paper doesn't state:
  the order of the dots (here random) and the background colour (white, as in the
  paper's search task).
- **Kalman filter:** earlier versions wrote `kalman_filter=on`, but the filter was never
  actually switched on (the call used does not exist in WebGazer 2.0.1), so old data was
  unfiltered. The column is now truthful, and the default stays off to match.
- **Sampling rate** is now computed within each point only. The old calculation included
  the gaps between points and under-reported the rate by roughly 15 %.
- **Samples are pruned from target onset** (first 100 ms), not from the first sample.
- **`valid_percent`** is now frames with a gaze estimate divided by all frames while a
  target was shown. The old value was close to 100 % by construction.
- Mouse clicks and movement before calibration no longer train the model; WebGazer's
  data is cleared at the start of each calibration.

## Experiments

Calibration does not carry over to a separate experiment page (WebGazer does not keep
it between pages in this set-up), so each experiment needs its own calibration.

## Attribution & licence

This tool bundles **WebGazer.js** (Brown HCI group), which is licensed under **GPLv3**.
Because of that, this combined work is distributed under **GPLv3** as well. It also uses
methods from Brand et al. (2021, *Behavior Research Methods*): the validation grid and
timing, the visual search task and its analysis; Li et al. (2020, *Scientific Reports*):
only the bank-card step for measuring the screen (their blind-spot test for viewing
distance is not used; distance comes from a tape measure or the camera estimate); and
Engbert & Kliegl (2003, *Vision Research*): the fixation detection in the search task.
