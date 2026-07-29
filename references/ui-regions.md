# UI region calibration

The shipped manifest includes an initial 1280x720 Chinese PC calibration for the shared loot-search header and one room-card pickup style. Other template-dependent detectors stay inactive until matching screenshots are supplied.

## Calibration procedure

1. Obtain lossless, original-resolution screenshots for inventory, the shared search panel, each container subtype, small/large safes, room-card pickup/use, ability activation, item detail, extraction success, and settlement screens.
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

## Room cards and abilities

- Treat `room_card_pickup` and `card_use` as different events. Calibrate the pickup prompt/card icon independently from the reader/door-opening sequence.
- Calibrate `card_prompt` from a stable card-use or door-unlock UI element. Avoid the room name, remaining-use count, timer, and changing card artwork when possible.
- Calibrate `ability_status` separately for each operator or ability HUD variant. A template for one operator does not prove detection for another.
- Test card and ability templates against ordinary interaction prompts, healing, weapon swaps, doors without cards, cooldown states, and spectator/death screens.
- Treat a visual effect alone as insufficient evidence for `ability_use` unless positive and negative samples show that it is stable and specific.

## Containers and safes

- Detect the shared right-side “正在搜索物资” panel as `loot_search` for recall. It is more stable than any single world object.
- Classify `subtype` from 0–2 seconds before the search panel appears. Include medical supply piles, travel bags, computer bags, weapon boxes, aviation boxes, advanced storage boxes, bird nests/eggs, courier boxes, and small safes in calibration.
- Do not infer a subtype from the inventory/search screen alone. Small safes may open directly into the shared search UI without a keypad.
- Split consecutive searches whenever the search UI closes for one sampled frame; do not merge different nearby containers into one raw event.
