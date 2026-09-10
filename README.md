# Gaze Check — webcam eye-tracking calibration & validation

A single-page, browser-based tool that calibrates a webcam eye tracker (WebGazer),
measures viewing distance, and validates data quality (accuracy, precision, sampling
rate) following the procedure of Brand et al. (2020). Runs entirely in the browser;
no video leaves the device — only gaze coordinates are recorded.

## Use it

Open the hosted page over **https** (e.g. GitHub Pages), allow the camera, and follow
the on-screen steps: set-up → distance → calibrate → validate → (optional) search task →
download CSV.

The camera and gaze tracking require a secure context (`https://` or `http://localhost`),
so it will not work by double-clicking the file locally — serve it or host it.

## Files

- `index.html` — the tool
- `webgazer-2.0.1.js` — the WebGazer library (loaded locally; CDN fallback in the page)
- MediaPipe FaceLandmarker (for the iris distance step) loads from a CDN at runtime

## Attribution & licence

This tool bundles **WebGazer.js** (Brown HCI group), which is licensed under **GPLv3**.
Because of that, this combined work is distributed under **GPLv3** as well. It also uses
methods from Brand et al. (2021, *Behavior Research Methods*), Li et al. (2020,
*Scientific Reports* — Virtual Chinrest), and Engbert & Kliegl (2003, *Vision Research*).

Before a formal release, add the full `LICENSE` (GPLv3) text and a citation file.
