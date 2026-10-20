# WebGazer Validation

A browser based study application for evaluating webcam eye tracking with a guided setup and validation procedure. The project uses [WebGazer.js](https://github.com/brownhci/WebGazer) for gaze prediction and adds its own participant interface, calibration tasks, quality checks, visual search task, and research data collection system.

The main question is how consistently people can set up webcam eye tracking and obtain usable gaze estimates on their own. The project is a research pilot. It is not a clinical eye tracking tool or a validated replacement for a dedicated eye tracker.

## Study procedure

The experiment includes the following tasks:

1. Optional participant information and questions about vision and previous eye tracker experience.
2. Screen measurement, camera permission, lighting, face positioning, and viewing distance checks.
3. Thirteen calibration targets used to provide training positions to WebGazer.
4. Five independent target locations to check calibration quality.
5. Twelve validation targets to measure gaze error, precision, and missing data.
6. An optional visual search task with 25 trials, two E targets, and 16 distractors in each trial.
7. A final screen where the participant chooses when to submit the study data.

Calibration and validation are kept separate. WebGazer uses the calibration positions to learn a relationship between eye features and screen coordinates. The validation targets are used to evaluate its predictions. These checks assume that participants follow the instructions and look at the intended target.

## Data recorded

When available, the application records predicted gaze coordinates in pixels, timestamps, gaze targets, screen and task information, missing predictions, interruptions, and sampling intervals. It also records calibration results, setup quality measurements, visual search responses, and optional participant information.

The application calculates gaze error, estimated accuracy and precision in visual degrees, gaze speed, and candidate fixation and saccade events. These are derived estimates rather than direct measurements of true eye movements. The visual angle calculations depend on screen measurements and estimated or measured viewing distance. Raw gaze records are retained to support alternative analyses.

## Application structure

The participant interface, FastAPI server, and researcher portal can run from the same Railway service. Raw submissions are saved to a private, S3 compatible object storage bucket. The participant page does not require an invitation or an account. Each browser session receives an internal identifier used to associate submitted records.

The research dashboard is separately password protected. It reports received and completed sessions and supports individual or whole study exports with CSV files, raw JSON records, summaries, and descriptive plots. Session counts are not necessarily counts of unique individuals because the study page is open.

| File | Purpose |
| --- | --- |
| `index.html` | Participant interface and experiment tasks |
| `webgazer-2.0.1.js` | Bundled WebGazer gaze prediction library |
| `quality.js` | Calibration and gaze quality calculations |
| `gaze_kinematics.js` | Estimated movement measurements from gaze predictions |
| `upload.js` | Local checkpoints and final data submission |
| `backend/main.py` | Participant API and storage operations |
| `backend/admin_portal.py` | Researcher authentication and access controls |
| `backend/admin_dashboard.html` | Researcher dashboard |
| `backend/export_reports.py` | CSV and plot exports |

## Data privacy and research status

Camera processing takes place in the participant's browser. The application is designed to submit gaze records and study responses, not webcam recordings. Optional names and study responses can still identify participants, and collected data must be handled under the relevant research consent and data security procedures.

This software has passed code tests and simulated browser tests, but it still requires full camera, upload, security, and multi participant testing in a live deployment. The gaze estimates are not independently verified against a reference eye tracker. The optional visual search task and calculated movement events should be interpreted with those limitations in mind.

Study datasets, access credentials, and participant exports are not included in this repository. The project reads deployment credentials from runtime environment variables. No environment files, passwords, password hashes, API tokens, or bucket access keys are distributed with the source code. The project reads deployment credentials from runtime environment variables. No environment files, passwords, password hashes, API tokens, or bucket access keys are distributed with the source code.

## References and acknowledgment

The gaze prediction library was developed by the [Brown WebGazer team](https://github.com/brownhci/WebGazer). The bundled `webgazer-2.0.1.js` file has been retained without modifying its tracking algorithm. Third party copyright and license notices are preserved.

Papoutsaki, A., et al. (2016). *WebGazer: Scalable Webcam Eye Tracking Using User Interactions*. Proceedings of IJCAI 2016.

The validation study design is informed by Brand et al. (2021), *Evaluating the data quality of the Gazepoint GP3 low cost eye tracker when used independently by study participants*. The present project uses WebGazer and does not reproduce the Gazepoint hardware or claim equivalent performance.

See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for library attribution.

## License

Project source code is distributed under the **GNU General Public License, version 3 (GPLv3)**. See [LICENSE](LICENSE). The included WebGazer bundle remains subject to the original WebGazer and bundled dependency notices. Research data are not part of the open source distribution.
