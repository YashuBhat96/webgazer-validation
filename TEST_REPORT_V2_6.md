# WebGazer study build test report

Tested locally on October 20, 2026. Automated software tests only; no live webcam or production Railway service was used.

Passed: JavaScript syntax checks, gaze quality unit tests, gaze movement calculations, browser smoke test with a simulated WebGazer engine, 300 simulated 18-item visual search layouts, upload queue test, and five FastAPI tests including consent enforcement, authentication separation, and storage receipts. The browser test confirms 50 visual search trials and that both a typed name and an explicit consent checkbox are required before proceeding.

The calibration and independent validation grid are 12 points each in 4 × 3 layouts. Both use 2,000 ms target display and 250 ms blank interval. Validation quality calculations exclude the first 100 ms after each target appears. The extra five point check was removed. Sessions without all 50 search trials are marked incomplete.

Not verified: live WebGazer webcam gaze predictions, actual participant following targets, external face model loading, real Railway uploads, recovery across browsers, timing jitter under heavy CPU load, research validity, or suitability for IRB-approved participant recruitment. The consent wording is a draft and must be reviewed by the study's IRB before recruitment.
