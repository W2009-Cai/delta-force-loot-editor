# UI region calibration

The shipped manifest is deliberately uncalibrated. Template-dependent detectors stay inactive until real 1920x1080 Chinese PC screenshots are supplied.

## Calibration procedure

1. Obtain lossless, original-resolution screenshots for inventory, container, safe, item detail, extraction success, and settlement screens.
2. Record each ROI as normalized `{x, y, w, h}` values in `assets/templates/manifest.json`.
3. Crop stable UI elements. Avoid player names, changing prices, timers, and animated backgrounds.
4. Save templates as PNG under `assets/templates/` and reference them from the manifest.
5. Run the detector against positive and negative samples. Raise thresholds until ordinary gameplay produces no candidates, then confirm all supplied positives still trigger.

Normalized coordinates are relative to the displayed frame after rotation handling. For a 1920x1080 screenshot, pixel rectangle `(px, py, pw, ph)` becomes:

```text
x = px / 1920
y = py / 1080
w = pw / 1920
h = ph / 1080
```

Use `item_detail` as the optional magnifier ROI. Keep the overlay away from the crosshair, minimap, backpack values, and bottom skill bar.
