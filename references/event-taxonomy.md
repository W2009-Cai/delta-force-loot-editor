# Event taxonomy and review strategy

Use a two-stage detector for loot interactions.

## Stage 1: high-recall event state

- `loot_search`: the shared right-side search panel is visible. Use one positive frame to enter and two consecutive misses to exit at 4 fps.
- `safe_open`: a safe opening is directly visible before the shared search panel. Small safes may have no keypad.
- `room_card_pickup`: a card lies in the world and the pickup prompt/icon is visible.
- `card_use`: the card is presented to a reader and the door unlocks or opens.
- `switch_pull`: a switch, power-control, lever, terminal, or route-enabling control is operated. Evidence can include a visible control device plus stable interaction text such as `ROTATE`, system-processing feedback, lever/knob motion, or an environmental state change. Do not classify this as `card_use` unless a card reader, room-card text, or door-unlock card evidence is visible.
- `transition_context`: a short route/arrival clip inserted before the next selected search/card/safe event when a long ordinary-running gap would otherwise make the cut feel spatially confusing. This is a reviewed editing aid, not a detector-only gameplay event.
- `high_value_loot`: a red or orange/gold item tile or reveal flash appears while `loot_search` or `inventory_open` overlaps.

Never merge room-card pickup with card use. Never use red/gold color alone outside a search or inventory state.

## Stage 2: subtype classification

Inspect 0–2 seconds before each `loot_search`. Record `subtype` only when the world object or interaction prompt is visible. Supported initial subtypes:

- `medical_supply_pile`
- `travel_bag`
- `small_safe`
- `computer_bag`
- `weapon_box`
- `aviation_box`
- `advanced_storage_box`
- `bird_nest`
- `courier_box`
- `unknown_container`

Store uncertain classifications as `unknown_container`; do not guess from loot contents. Adjacent searches remain separate raw events even when their buffered editing ranges later merge.

## User feedback

Treat user-confirmed timestamps as regression labels. Add corrected events with `review_status: user_confirmed`. Keep an incorrect or over-broad original candidate with `review_status: user_rejected` and `auto_selected: false`. Re-run the audit page after every correction so subtype, status, notes, and debug evidence remain visible.
