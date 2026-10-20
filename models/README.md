# Face models must be installed before a controlled deployment

This directory intentionally contains **no model weights**. The WebGazer 2.0.1 bundle may request BlazeFace and FaceMesh data hosted on TFHub. The original app tries local files first and remote files second. Fetch requests map these paths:

- `models/blazeface/model.json` and all binary shards referenced by that JSON
- `models/facemesh/model.json` and all binary shards referenced by that JSON

Before participant data collection, obtain appropriately licensed, compatible TensorFlow.js assets, pin exact versions and hashes, place each `model.json` and every referenced shard beneath the corresponding model directory, and test actual model loading in Chrome and Edge. A blank placeholder JSON is not a valid model. This release retains the original external fallback so the prototype can still attempt to work, but successful inference was **not** verified here.
