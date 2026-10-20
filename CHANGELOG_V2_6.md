# October 2026 protocol update

This version adds a required typed name and consent checkbox to the opening screen, with a versioned consent acknowledgment saved as the first study submission batch. The backend requires consent before accepting completion.

Calibration trains WebGazer at 12 positions in a 4 × 3 layout, with each point appearing for two seconds and a 250 ms blank interval. Separate validation uses 12 different positions in a 4 × 3 grid with the same timings. The initial 100 ms after each target appears is excluded from the accuracy and precision calculation. The extra five point check was removed.

The visual search task now has 50 trials (2 targets, 16 distractors per trial). Ending early is allowed, but those sessions are marked incomplete for the researcher dashboard. WebGazer 2.0.1 itself is unchanged.

Software tests verify syntax, basic browser flow, quality metrics, 50 trial generation, and backend consent enforcement. Actual webcam accuracy, face model loading, participant performance, and live Railway object storage have not been verified.
