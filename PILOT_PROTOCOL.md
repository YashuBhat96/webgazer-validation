# Study plan: independent webcam gaze validation

**Status:** Research proposal and functional prototype. Not validated against a reference eye tracker. Thresholds and timings are implementation defaults, not published parameters directly attributed to Brand et al.

## Research question

Can an independently operated WebGazer setup, with guided camera positioning and calibration, produce consistent region level fixation estimates suitable for a proposed research task? How frequently can participants establish usable calibration, and how do accuracy, spatial precision, data availability, and item level gaze discrimination differ across participants, visits and equipment?

## Brand et al. comparison

Brand, Diamond, Thomas and Gilbert Diamond (2021) tested whether participants independently using Gazepoint GP3 produced data quality comparable to experts. N=20 participants trained and returned roughly one week later. Their two tasks assessed (1) gaze accuracy and precision and (2) visual search target fixations; sampling intervals were also studied. The study reported 92.5% sensitivity and 76.8% specificity for participant detected target fixations, and mean intersample interval 16.99 ± 3.0 ms for participants versus 16.43 ± 2.3 ms for experts. **These are Gazepoint results, not WebGazer expectations.** [DOI](https://doi.org/10.3758/s13428-020-01504-2).

| Dimension | Comparable design goal | This WebGazer implementation / difference |
|---|---|---|
| Independent operation | Training followed by independent followup | Researcher controls visit scheduling and any guided versus independent setup; no participant facing dropdown |
| Expert reference | Expert users completing same measures | No expert/participant field is included; collect an optional previous eye tracker experience yes/no answer |
| Calibration validity | Determine usability before main tasks | 13 point WebGazer training plus independent 5 point screen, both software specific |
| Spatial data quality | Accuracy and precision against known target position | 12 known target positions, 2 s each. Timing is prototype parameter, not proven exact paper match |
| Lost data | Sampling and quality during trials | Null callbacks, out of bounds, time bins and long gaps; no assumed fixed camera sampling rate |
| Visual search | Two targets among distractors, gaze fixation outcome | Two among 16, 25 rounds (as in the uploaded original) with clicks, trial labels, gaze; item target discrimination distinct from verified fixation detection sensitivity |
| Reference gaze | GP3 hardware outputs | No simultaneous independently verified reference. Adding a synchronized hardware comparator would materially strengthen validation |
| Different user groups | Experts versus participants | No expert group assignment is captured automatically; prospective expert comparisons require a separately planned group definition |

The accessible source for the Brand paper was the abstract and article preview. We did not verify its complete task timings, exact visual stimulus geometry, AOI definitions, fixation classification, or statistical analysis. Obtain the full methods or materials from the authors before claiming a close replication. Our 13 point calibration and 12 point spatial grid were inherited from the user's original software and **must not be presented as identical to Brand's procedure**.

## Recommended minimum validation sequence

1. **Engineering pilots:** Run with a real camera and the specified face model weights, including permission denial, network failure, extreme glare, glasses, out of frame, no callbacks, tab changes, window changes, prolonged search, missing downloads, and external display tests.
2. **Feasibility pilots:** Enrol a small varied group and record setup completion, number of calibration attempts, reason for screen failure, point level errors by location, gap distributions and dropout. Include participants who fail calibration in usability summaries rather than reporting only successful cases.
3. **Participant versus expert test:** If comparing expert versus inexperienced operators, recruit both deliberately and match setup conditions; the yes/no past experience question does not by itself establish expert competence.
4. **Training versus testing:** In Visit 1, instruct the participant in operating the interface with researcher guidance; in Visit 2, repeat after approximately one week without researcher help, with actual assistance recorded separately. This human training is distinct from WebGazer calibration, which is repeated at each visit. Keep the originally specified 25 visual search trials fixed across visits, and freeze code and thresholds before comparison.
5. **Criterion or convergent validation (recommended):** If available, collect synchronized WebGazer and independent eye tracker data for the *same* viewing trials. Align clocks, screen geometry and sample timestamps. Measure detection error separately for primary fixations and AOI categories.
6. **Downstream use:** Test the specific research task with its actual stimulus geometry; larger AOIs may be analyzable when tiny face/word regions and first saccade estimates are not.

## Primary and supplementary metrics

Primary: proportion passing the predeclared 5 point screen; mean of per point Euclidean error in CSS px and approximate degrees for tape measured distances; maximum location error; 12 point usable region count; usable time coverage (100 ms bins); per point dropout reasons; and intersample interval distribution. Mean gaze offset is computed as distance from target to average recorded gaze and is **not interchangeable** with the mean of per sample Euclidean errors. `gaze_points` includes both.

Precision: root mean square of within location distances from the location's mean gaze. Also save RMS successive sample distance as a separate diagnostic. These are calculated for relatively steady target viewing windows; they are not automatically fixation event precision as defined by every hardware study. The window is 300 to 2000 ms after the new target appears.

Secondary: task completion, correct/incorrect target clicks, search time, and item level target fixation detector rates (not genuine detector sensitivity without reference eye tracking). Sampling frequency is reported as callbacks per second **only for usable periods**, separately from missing interval coverage.

## Precommitments and quality reporting

Report both screen eligible and ineligible participants (do not delete unsuccessful participants from feasibility denominators). Do not change AOI width or fixation duration thresholds post hoc to maximize AUC. Report an overall screen quality summary as an initial *screen*, never as proof of valid fine grained gaze. Separate unmeasured viewing distance sessions from tape measured sessions for degrees and report both counts. Restrict software changes during the study; store build identifier, browser details and WebGazer model provenance.

For participant studies, ethics review, consent, privacy, eligibility rules, sample size and recruitment procedures remain a separate responsibility of the study team.

## Version 2.3 changes

The participant-facing training/testing and expert/participant fields have been removed. The interface collects optional name, optional sex assigned at birth, and a yes/no history of previous use of eye trackers. The present open enrollment version uses a single anonymous pilot session type. The team should define participant followup linkage separately if a repeated visit design is later added. Exactly 25 search trials remain.

During the experiment, data are checkpointed to the participant's browser only. The participant must deliberately press the large SUBMIT STUDY DATA button at the end to send data. A reopened session with pending data offers explicit recovery and labels an incomplete attempt as partial. Browser storage is not guaranteed durable across private browsing sessions, cleared storage, or different devices.

The new analysis files save pixel gaze positions, approximate per-axis gaze angles and target error angles, sample timing and step velocities, plus candidate fixations and saccades derived with an exploratory velocity threshold. **These movements are not provided or validated by WebGazer itself.** Retain raw data, predeclare parameters, and perform hardware validation if study conclusions depend on true saccade detection.
