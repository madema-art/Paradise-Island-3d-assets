# Castaway animation library

Generated from `assets/castaway/castaway_clips.json` by `tools/castaway/make_docs.py`. **142 clips** at 30 fps (**138 verified**, **4 in development**) plus **31 upper-body layer variants** (`<clip>__upper`).

Status rules: *verified* = reviewed frame by frame in skinned Three.js contact sheets of the real GLB **and** the automatic QA passes (IK reach error ≤ 25 mm, no bones more than 30 mm below the ground plane unless the clip is in water or a canoe, hands on the staff/paddle within tolerance). *In development* = authored and playable, with the issue listed in `status_note`.

## Conventions

- **axes**: glTF: +Y up, the character faces +Z; Blender bone frames equal glTF node frames (no axis swizzle on animation channels)
- **root motion**: locomotion/transition clips keep the `root` bone fixed; world motion is exported as speed/yaw curves; anchored clips bake the root relative to a named anchor; vertical climbs are in place with a climb speed
- **loops**: loop clips are closed by repeating the first frame as the last keyframe
- **upper body layers**: clips with `upper_body_variant` have `<name>__upper` animations containing only the bones in `upper_body_mask`: play them additively over a base loop (idle/walk) by weighting the two actions per bone group (or by disabling the lower-body tracks)
- **status**: verified = reviewed frame by frame in skinned Three.js contact sheets of the real GLB and QA metrics within tolerance; in_development = authored, with listed issues

## Animation packs

| File | Clips | Size |
|---|---|---|
| `Castaway.glb` | model + 6 core clips (idle_relaxed, idle_breathe, idle_look_around, walk, walk_brisk, run) | 10.35 MB |
| `Castaway_anim_locomotion.glb` | 17 (+ upper-body layers) | 1.18 MB |
| `Castaway_anim_posture.glb` | 11 (+ upper-body layers) | 0.88 MB |
| `Castaway_anim_staff.glb` | 6 (+ upper-body layers) | 0.47 MB |
| `Castaway_anim_personality.glb` | 36 (+ upper-body layers) | 4.60 MB |
| `Castaway_anim_survival.glb` | 15 (+ upper-body layers) | 1.60 MB |
| `Castaway_anim_fishing.glb` | 15 (+ upper-body layers) | 1.33 MB |
| `Castaway_anim_canoe.glb` | 11 (+ upper-body layers) | 0.92 MB |
| `Castaway_anim_wildlife.glb` | 14 (+ upper-body layers) | 1.34 MB |
| `Castaway_anim_climbing.glb` | 12 (+ upper-body layers) | 1.03 MB |
| `Castaway_anim_water.glb` | 5 (+ upper-body layers) | 0.38 MB |

Packs are skeleton-only GLBs: load the model once, then load a pack with `GLTFLoader` and pass `gltf.animations` to the `AnimationMixer` of the model (tracks bind by node name).

## Base loops (32)

### idle

| Clip | s | Play | Status | Root motion | Props | Description |
|---|---|---|---|---|---|---|
| `idle_relaxed` | 8.00 | loop | verified | in_place | - | Relaxed standing idle: breathing, a slow weight shift, small head and eye drift, blinks. |
| `idle_breathe` | 5.00 | loop | verified | in_place | - | Quiet standing with slow, deep breathing (contemplative); almost still. |
| `idle_weight_shift` | 10.00 | loop | verified | in_place | - | Standing idle that shifts weight from one leg to the other, rolling the hips; one foot re-plants slightly. |
| `idle_look_around` | 9.00 | loop | verified | in_place | - | Standing and curiously looking around: head and eyes lead, shoulders follow, slow scan left, up, right. |
| `idle_staff` | 9.00 | loop | verified | in_place | staff | Standing with the staff planted at his right side, right hand resting on it at hip height; breathing, weight shift, slow look around. |
| `idle_staff_lean` | 10.00 | loop | verified | in_place | staff | Leaning forward on the staff planted in front of him, both hands stacked on top; resting, gazing out, slow breathing. |

### locomotion

| Clip | s | Play | Status | Root motion | Props | Description |
|---|---|---|---|---|---|---|
| `walk` | 1.07 | loop | verified | in_place 1.3 m/s | - | Normal walk. In place: set the AnimationAction timeScale = controller speed / 1.30 m/s. Feet are planted in world space. |
| `walk_brisk` | 0.80 | loop | verified | in_place 1.9 m/s | - | Brisk, purposeful walk with a longer stride and bigger arm swing (1.9 m/s). |
| `run` | 0.67 | loop | verified | in_place 4.3 m/s | - | Lanky long-striding run with flight phase (4.3 m/s): strong arm drive, forward lean, loose hands. |
| `walk_staff` | 1.13 | loop | verified | in_place 1.2 m/s | staff | Walking with the staff held in the right hand, planted ahead on each left step. In place: timeScale = speed / 1.20. |

### posture

| Clip | s | Play | Status | Root motion | Props | Description |
|---|---|---|---|---|---|---|
| `sit_idle` | 7.00 | loop | verified | in_place | - | Seated on the ground, knees up, hands resting on the knees: breathing, slow looking around at the sea. |
| `kneel_idle` | 6.00 | loop | verified | in_place | - | Kneeling quietly (both knees down), breathing, small head turns. |
| `sleep_loop` | 6.00 | loop | verified | in_place | - | Sleeping on the back: slow breathing (chest/belly rise, jaw relaxed and slightly open), eyes closed, one arm on the chest. |

### canoe

| Clip | s | Play | Status | Root motion | Props | Description |
|---|---|---|---|---|---|---|
| `canoe_sit_idle` | 9.00 | loop | verified | in_place | canoe | Seated in the canoe on the thwart, letting the right hand trail in the water, gazing around the lagoon, swaying gently with the hull. |
| `canoe_paddle` | 2.40 | loop | verified | in_place 1.0 m/s | canoe, paddle | Seated paddling on the right side: reach forward, plant the blade, a long draw back with torso rotation, lift and recover. |
| `canoe_paddle_left` | 2.40 | loop | verified | in_place | canoe, paddle | Seated paddling on the left side (mirror of `canoe_paddle`). |
| `canoe_paddle_hard` | 1.60 | loop | verified | in_place | canoe, paddle | Fast, powerful paddling (right side) for returning to shore or racing: short cycle, deeper lean. |
| `canoe_drift` | 8.00 | loop | verified | in_place | canoe, paddle | Drifting: paddle laid across the knees, both hands resting on it, slowly scanning the water and shore. |
| `canoe_fish_seated` | 10.00 | loop | verified | in_place | canoe, staff | Fishing from the seated position: pole held in both hands out over the side, patient, tiny tip twitches. |
| `canoe_reel_in` | 2.00 | loop | verified | in_place | canoe, staff | Reeling in a fish from the canoe: rod tip high and bowed, left hand hauling line, torso rocking with each pull. |
| `canoe_pull_on_land` | 2.40 | loop | verified | in_place | canoe, rope | Hauling the canoe up the beach by its bow rope: wide braced stance, leaning back and heaving, hand over hand. |

### climbing

| Clip | s | Play | Status | Root motion | Props | Description |
|---|---|---|---|---|---|---|
| `tree_climb_up` | 2.40 | loop | verified | vertical climb 0.14 m/s | palm | Climbing a leaning palm trunk, hand over hand and foot over foot (0.14 m/s upwards): hugging the trunk with the soles flat against it. In-place; the virtual root rises at climb_speed. |
| `tree_climb_down` | 2.40 | loop | verified | vertical climb -0.14 m/s | palm | Climbing back down the trunk feet first, one limb at a time (0.14 m/s downward). In-place; the virtual root descends. |
| `tree_hold_rest` | 6.00 | loop | verified | in_place | palm | Resting mid-climb: arms and legs locked around the trunk, forehead dropping towards the bark, deep breaths. |
| `clamber_rocks` | 1.93 | loop | verified | in_place 0.45 m/s | - | Scrambling up a jumble of rocks on all fours-ish: deep forward lean, hands slapping onto holds alternately with the opposite foot stepping up (0.45 m/s). |
| `balance_uneven` | 4.00 | loop | verified | in_place | - | Balancing on one foot on unstable ground: arms out and wobbling, torso counter-swaying, free foot hovering for a recovery step. |
| `high_lookout` | 10.00 | loop | verified | in_place | - | Standing tall on a high perch, feet planted wide against the wind, one fist on the hip, the other hand shading his eyes while he scans the horizon. |

### water

| Clip | s | Play | Status | Root motion | Props | Description |
|---|---|---|---|---|---|---|
| `wade` | 1.47 | loop | verified | in_place 0.95 m/s | - | Wading through knee-deep water (0.95 m/s): high lifted knees, arms held out and low for balance, slower rhythm. timeScale = speed / 0.95. |
| `swim_crawl` | 1.60 | loop | **in development** | in_place | - | Front crawl at the surface: alternating overarm strokes, flutter kick, body roll with a breath to the side on every other stroke. |
| `swim_breaststroke` | 2.60 | loop | **in development** | in_place | - | Relaxed breaststroke: pull, breathe with the head up, frog kick and a long glide with the arms stretched forward. |
| `float_on_back` | 8.00 | loop | verified | in_place | - | Floating on his back at the surface, arms spread and sculling gently, slow deep breaths, eyes closed against the sun. |
| `tread_water` | 3.00 | loop | **in development** | in_place | - | Treading water upright with the root sunk 0.55 m: eggbeater leg circles, hands sculling at the sides, chin just above the surface. |

## Transitions (32)

### transition

| Clip | s | Play | Status | Root motion | Props | Description |
|---|---|---|---|---|---|---|
| `walk_start` | 1.47 | once | verified | path | - | Standing to walking: the left foot leads, speed ramps 0 -> 1.30 m/s over 1.3 s (feed the controller the exported speed curve). Ends at the left heel strike = `walk` loop phase 0. |
| `run_start` | 1.10 | once | verified | path | - | Standing to running: crouched lean, three accelerating strides, ends at the left heel strike = `run` loop phase 0. |
| `walk_stop` | 1.53 | once | verified | path | - | Walking to standing: starts at a left heel strike (`walk` phase 0), speed decays 1.30 -> 0 m/s, the right foot leads the stop and the left closes beside it. |
| `walk_brisk_stop` | 1.27 | once | verified | path | - | Brisk walk to standing (starts at `walk_brisk` phase 0). |
| `run_stop` | 1.47 | once | verified | path | - | Running to standing: braking strides with a backward lean, ends upright (starts at `run` phase 0). |
| `turn_left_90` | 1.87 | once | verified | path | - | Stepping turn on the spot, 90 degrees to the left (head and chest lead, feet re-plant). The controller rotates the heading using the exported yaw curve; the root bone does not rotate. |
| `turn_right_90` | 1.87 | once | verified | path | - | Stepping turn on the spot, 90 degrees to the right. |
| `turn_180` | 2.10 | once | verified | path | - | About-face: 180 degree stepping turn to the left in four steps. |
| `run_cut_left` | 1.00 | once | verified | path | - | Sudden 70 degree direction change to the left while running: speed dips ~28 %, body leans into the turn, head leads. |
| `run_cut_right` | 1.00 | once | verified | path | - | Sudden 70 degree direction change to the right while running. |
| `walk_staff_start` | 1.57 | once | verified | path | staff | Standing with the staff to walking with it: the staff lifts with the left foot, speed ramps to 1.20 m/s. Ends at `walk_staff` phase 0. |
| `walk_staff_stop` | 1.67 | once | verified | path | staff | Walking with the staff to standing: starts at `walk_staff` phase 0, the staff is planted at his side for the final step. |

### posture

| Clip | s | Play | Status | Root motion | Props | Description |
|---|---|---|---|---|---|---|
| `sit_down` | 2.40 | once | verified | in_place | - | Standing to sitting on the ground: knees bend, weight sinks back, hands reach behind to lower the pelvis, then settle with the hands on the knees (ends in the `sit_idle` pose). |
| `stand_up` | 2.10 | once | verified | in_place | - | Sitting on the ground to standing: leans forward, feet pull in, hands push off the ground, rises through a crouch to a relaxed stand. |
| `kneel_down` | 1.50 | once | verified | in_place | - | Standing to kneeling on both knees (shins on the ground behind, hands settle on the thighs). |
| `kneel_rise` | 1.65 | once | verified | in_place | - | Rising from kneeling: one foot steps forward, hands push on the knee, stand up straight. |
| `lie_down` | 2.80 | once | verified | in_place | - | Standing to lying on the back (head ends toward the character's rear): crouch, sit, recline on the hands, lie flat. |
| `fall_asleep` | 5.00 | once | verified | in_place | - | Lying on the back, drifting off: eyelids droop and close, one arm settles on the chest, jaw softens, breathing slows into the `sleep_loop` pose. |
| `wake_up` | 2.20 | once | verified | in_place | - | Waking on the back: groans, jaw works, eyes screw up then open, blinks, looks around; ends awake and lying down. |
| `stretch_after_sleep` | 4.40 | once | verified | in_place | - | Sitting up from lying down, then a big yawning stretch with both arms overhead and a satisfied settle (ends in a seated pose). |

### interaction

| Clip | s | Play | Status | Root motion | Props | Description |
|---|---|---|---|---|---|---|
| `staff_pickup` | 4.00 | once | verified | in_place | staff | Bends down, picks the staff up from the ground at his right side and plants it beside him (ends in `idle_staff`). |

### survival

| Clip | s | Play | Status | Root motion | Props | Description |
|---|---|---|---|---|---|---|
| `sit_on_rock` | 1.80 | once | verified | in_place | - | From standing, lowers himself onto a rock or log seat (0.50 m): knees bend, hands settle on the thighs. |
| `rise_from_rock` | 1.70 | once | verified | in_place | - | Leans forward, pushes off the thighs and stands up from a 0.50 m rock/log seat. |

### fishing

| Clip | s | Play | Status | Root motion | Props | Description |
|---|---|---|---|---|---|---|
| `spear_aim` | 1.40 | once | verified | in_place | staff | Spots a fish: sinks lower, draws the spear back and locks the tip onto it, eyes narrowed, breath held. |

### canoe

| Clip | s | Play | Status | Root motion | Props | Description |
|---|---|---|---|---|---|---|
| `canoe_board` | 3.20 | once | verified | anchored | canoe | Steps from the beach into the canoe: grips the gunwale, swings a leg over the rail, steps in and turns to face the bow. Root is baked relative to the shore anchor (beside the hull). |
| `canoe_sit_down` | 2.20 | once | verified | anchored | canoe | Lowers himself onto the thwart seat and settles, hands coming to rest on the thighs (hull floor 0.12 m, seat 0.30 m). |
| `canoe_exit` | 3.00 | once | verified | anchored | canoe | Climbs out of the canoe onto the beach: stands, turns, steps a leg over the gunwale and walks clear. Root baked relative to the shore anchor. |

### climbing

| Clip | s | Play | Status | Root motion | Props | Description |
|---|---|---|---|---|---|---|
| `reach_for_handhold` | 2.20 | once | verified | in_place | - | Reaches high for a rock or branch, stretching onto his toes, tests the hold with a tug, then commits his weight. |
| `climb_approach_tree` | 2.60 | once | verified | in_place | - | Stops at a palm trunk, lays a hand on the bark and looks up the length of it, sizing up the climb. |
| `climb_onto_boulder` | 3.50 | once | verified | anchored | boulder | Hauls himself onto a 0.75 m boulder: hands on the lip, one foot on a ledge, chest over the edge, a knee up onto the top and a push to stand. Root baked relative to the anchor at the foot of the rock. |
| `climb_down_boulder` | 3.50 | once | verified | anchored | boulder | Lowers himself off the 0.75 m boulder facing it (the climb played in reverse): lies on the edge, feels for the ledge, drops to the ground. |
| `step_down_rock` | 1.70 | once | verified | anchored | rock | Steps down off a 0.5 m rock: a controlled reach with the left foot, weight transfer, soft landing with the knees and arms out for balance. |

## Interaction actions (36)

### survival

| Clip | s | Play | Status | Root motion | Props | Description |
|---|---|---|---|---|---|---|
| `drink_cupped_hands` | 8.00 | once | verified | in_place | - | Crouches at the water's edge, scoops water with cupped hands and drinks twice, then rises and wipes his beard. |
| `wipe_mouth` | 1.50 | once | verified | in_place | - | Wipes the mouth and beard with the back of the right hand after drinking or eating. |
| `coconut_pickup` | 3.80 | once | verified | in_place | coconut | Crouches, picks a coconut up off the sand in his right hand and rises, holding it out to inspect it. |
| `coconut_crack` | 4.20 | once | verified | in_place | coconut, rock | Cracks a coconut with three sharp blows against a rock (held in the right fist), then pulls the shell apart with both hands. |
| `coconut_drink` | 4.40 | once | verified | in_place | coconut | Raises the opened coconut to his mouth with both hands, tips his head back and drinks, then lowers it with a satisfied face. |
| `eat_food` | 6.00 | loop | verified | in_place | food | Eating a piece of fruit/fish held in the right hand: bite, chew with cheeks working, next bite; left hand cups below. |
| `rest_on_rock` | 10.00 | loop | verified | in_place | - | Sitting on a rock or log (seat height 0.50 m), forearms resting on the thighs, gazing slowly around; breathing and small posture shifts. |
| `tend_fire` | 8.00 | loop | verified | in_place | firewood | Kneeling at the fire: feeds a stick into the flames, leans in and blows on the embers, eyes squinting against the heat. |
| `turn_fish_on_fire` | 6.00 | loop | **in development** | in_place | fish, skewer | Kneeling by the fire, turning a fish on a skewer over the flames with both hands, rolling the wrist and watching it cook. |
| `rest_by_fire` | 10.00 | loop | verified | in_place | - | Sitting on the ground hugging his knees, staring into the fire; slow breathing, drowsy blinks, firelight squint. |
| `prepare_food` | 6.00 | loop | verified | in_place | knife_stone, food | Sitting on the ground preparing food on a flat stone: left hand holds the item, right hand chops/pounds with a rhythmic beat. |
| `shelter_from_rain` | 3.00 | loop | verified | in_place | - | Hunched against the rain: shoulders up, one arm raised overhead as a makeshift roof, the other clutched to the chest, squinting. |
| `sit_watching_rain` | 8.00 | loop | verified | in_place | - | Sitting under shelter watching the rain: holds a palm out to catch drops, tips his head up toward the sky, relaxed breathing. |

### fishing

| Clip | s | Play | Status | Root motion | Props | Description |
|---|---|---|---|---|---|---|
| `fish_wait_stand` | 12.00 | loop | verified | in_place | staff | Standing and fishing, pole held two-handed with the tip over the water: patient weight shifts, line checks, small twitches of the tip. |
| `fish_prepare_rod` | 5.00 | once | verified | in_place | staff | Takes the pole in both hands, runs the left hand up the shaft checking the line guides and lashings, flexes it and settles into the ready stance. |
| `fish_cast` | 3.20 | once | verified | in_place | staff | Casting: the pole sweeps back over the shoulder, then whips forward and releases the line; follow-through settles with the tip over the water. |
| `fish_reel_in` | 2.00 | loop | verified | in_place | staff | Reeling in a fish: tip held high bowed under strain, left hand hauls the line hand-over-hand, body leaning back with each pull. |
| `fish_lift_catch` | 2.60 | once | verified | in_place | staff, fish | Swings the pole up and back to land the fish, catches the line with the left hand and holds the catch out in front. |
| `fish_inspect_catch` | 5.00 | once | verified | in_place | fish | Holds the freshly caught fish in both hands, turns it over to size it up, pleased half-smile and a raised brow. |
| `fish_reset` | 3.40 | once | verified | in_place | staff | Reels the slack line in by hand, checks the hook, re-baits and returns to the ready stance. |
| `spear_stance_idle` | 6.00 | loop | verified | in_place | staff | Spearfishing stance: knees bent, wide split stance, spear held two-handed pointing down at the water, scanning for fish. |
| `spear_thrust` | 1.40 | once | verified | in_place | staff | Explosive spear thrust into the water: back leg drives, torso lunges forward, both arms extend and the tip plunges. |
| `spear_recover_miss` | 2.40 | once | verified | in_place | staff | The fish darts away: pulls the spear out of the water, straightens up and shakes his head with a rueful grimace. |
| `spear_catch_lift` | 3.00 | once | verified | in_place | staff, fish | Impaled a fish! Hauls the spear up out of the water with the fish wriggling on the tip and holds it up with a triumphant grin. |

### wildlife

| Clip | s | Play | Status | Root motion | Props | Description |
|---|---|---|---|---|---|---|
| `observe_animal` | 10.00 | loop | verified | in_place | - | Standing very still watching an animal: slow head and shoulder scan, one hand shading the eyes against the glare. |
| `birdwatch` | 9.00 | loop | verified | in_place | - | Tracks birds flying overhead: head thrown back following the arc of the flock, hand shading the eyes, a delighted half-smile. |
| `track_animals` | 9.00 | loop | verified | in_place | - | Crouched reading tracks in the sand: scanning the ground, brushing the prints with the fingertips, following the trail with his eyes. |
| `approach_carefully` | 1.67 | loop | verified | in_place 0.55 m/s | - | Creeping forward in a low, quiet crouch (0.55 m/s): knees bent, heel-toe placement, arms out for balance, eyes locked on the target. timeScale = speed / 0.55. |
| `stalk_rat` | 1.87 | loop | verified | in_place 0.45 m/s | staff | Stalking prey with the spear held low in both hands (0.45 m/s): deep crouch, slow silent steps, tip trained on the target. timeScale = speed / 0.45. |
| `spear_thrust_ground` | 1.30 | once | verified | in_place | staff | Lunging spear stab downward at small ground prey (rat/crab): the back foot drives, the tip drives into the sand. |
| `spear_ground_recover` | 2.20 | once | verified | in_place | staff | Missed the quarry: pulls the spear from the sand, rises, shakes his head and plants the staff at his side. |
| `sprint_away` | 0.57 | loop | verified | in_place 5.4 m/s | - | All-out panicked sprint (5.4 m/s): maximum lean, flailing arms, wide eyes. timeScale = speed / 5.4. |
| `run_look_back` | 0.57 | loop | verified | in_place 5.4 m/s | - | Fleeing at a sprint while glancing back over the left shoulder at what is chasing him: torso and head twisted ~90 degrees, eyes wide. |
| `chase_monkey` | 0.70 | loop | verified | in_place 3.9 m/s | - | Running after a monkey that has stolen something: arms reaching and grabbing, jaw open shouting, half grimace half grin (3.9 m/s). |
| `catch_breath` | 4.40 | loop | verified | in_place | - | Bent over with hands on knees, heaving for breath after the run: heavy panting, shoulders rising, head hanging. |

### climbing

| Clip | s | Play | Status | Root motion | Props | Description |
|---|---|---|---|---|---|---|
| `look_down_from_height` | 3.40 | once | verified | in_place | - | Peers over the edge of a high drop: leans forward from a braced stance, hand pressed on the knee, eyes wide, a nervous swallow. |

## Emotional reactions (17)

### personality

| Clip | s | Play | Status | Root motion | Props | Description |
|---|---|---|---|---|---|---|
| `laugh_quiet` | 3.40 | once | verified | in_place | - | Quiet amused chuckle: shoulders shake softly, eyes crinkle, head tips slightly. |
| `laugh_hearty` | 4.20 | once | verified | in_place | - | Big belly laugh: head thrown back, torso rocking and folding forward, one hand on the belly, wide open mouth. |
| `frustration` | 3.00 | once | verified | in_place | - | Tight-jawed frustration: fists clench, shoulders rise, sharp head shake, a hand rakes through the hair. |
| `disappointment` | 3.40 | once | verified | in_place | - | Disappointed slump: shoulders and head drop, slow head shake, small sigh, hands hanging limp. |
| `surprise` | 1.80 | once | verified | in_place | - | Startled surprise: weight jerks back, eyes widen, brows shoot up, hands fly open in front of the chest. |
| `excitement` | 2.60 | once | verified | in_place | - | Excited little hops with both fists pumping, big grin, head bobbing. |
| `confusion` | 3.20 | once | verified | in_place | - | Puzzled: head tilts and turns, one eyebrow climbs, one hand opens palm-up in a questioning shrug. |
| `sigh` | 3.40 | once | verified | in_place | - | Deep breath in (chest and shoulders rise) and a long audible sigh out with the shoulders sagging. |
| `celebrate` | 3.40 | once | verified | in_place | - | Triumphant celebration: crouch, leap with both fists overhead, land and punch the air with a roar of joy. |
| `embarrassed_recover` | 3.40 | once | verified | in_place | - | Sheepish embarrassment after a blunder: rubs the back of his neck, shy lopsided grin, looks away, shuffles. |
| `shrug` | 2.20 | once | verified | in_place | - | Classic 'who knows?' shrug: shoulders up, palms out and up, brows raised, mouth pulled down. |

### fishing

| Clip | s | Play | Status | Root motion | Props | Description |
|---|---|---|---|---|---|---|
| `fish_bite_reaction` | 1.60 | once | verified | in_place | staff | A bite! The tip dips hard, he starts, then strikes: a sharp pull up to set the hook, eyes wide. |
| `fish_celebrate` | 3.20 | once | verified | in_place | fish | Holds the fish overhead and whoops with joy, bouncing on his toes with the free fist pumping. |
| `fish_fail` | 3.20 | once | verified | in_place | staff | The fish slips the hook: the pole whips up as the line goes slack, then the tip sags and he exhales and shakes his head. |

### wildlife

| Clip | s | Play | Status | Root motion | Props | Description |
|---|---|---|---|---|---|---|
| `curious_reaction` | 2.20 | once | verified | in_place | - | Something rustles: head snaps toward the sound, then he leans in, brows raised, trying to see what it is. |
| `startled` | 1.40 | once | verified | in_place | - | Sudden fright: jumps back with arms flung out, eyes and mouth wide open, then freezes tense. |
| `laugh_after_chase` | 4.60 | once | verified | in_place | - | Collapses into helpless laughter after the chase: hands on knees, back heaving, tears of mirth. |

## Personality actions (25)

### personality

| Clip | s | Play | Status | Root motion | Props | Description |
|---|---|---|---|---|---|---|
| `head_scratch` | 3.20 | once | verified | in_place | - | Scratches the back/top of his head with the right hand while thinking, head tilted. |
| `contemplation` | 6.00 | loop | verified | in_place | - | Thoughtful pose: right hand to the chin, left arm folded across the belly, gaze drifting out to sea. |
| `yawn` | 3.40 | once | verified | in_place | - | Big tired yawn: head tips back, jaw wide, eyes squeezed shut, a fist partly covers the mouth, left arm stretches out. |
| `stretch_standing` | 4.30 | once | verified | in_place | - | Standing full-body stretch: arms reach overhead, back arches, a lean to each side, with a satisfied exhale. |
| `whistle` | 4.00 | once | verified | in_place | - | Casual whistling: lips pursed, head bobbing to the tune, one hand tucked at the hip, the other swinging. |
| `hum_sing` | 6.00 | once | verified | in_place | - | Humming/singing to himself: slow sway, head nodding on the beat, mouth shaping vowels, relaxed arms keeping time. |
| `shout` | 2.20 | once | verified | in_place | - | Shouting across the water: hands cupped around the mouth, head back, wide mouth. (Hands ride on the head.) |
| `talk_to_self` | 7.00 | loop | verified | in_place | - | Muttering to himself: mouth moving, small explanatory hand gestures, head turning and nodding as if arguing both sides. |
| `dance_sway` | 4.00 | loop | verified | in_place | - | Slow flowing sway dance: hips roll side to side with bent knees, arms drifting over the head in opposite waves. |
| `dance_hop` | 2.00 | loop | verified | in_place | - | Lively one-legged hop dance: alternates bouncing on each foot with a kick, arms pumping with the beat. |
| `dance_stomp` | 2.40 | loop | verified | in_place | - | Grounded tribal-style stomp dance: deep knee bend, alternating stamping steps, forearms driving at the chest. |
| `dance_hula` | 4.00 | loop | verified | in_place | - | Hip-circling island sway with rippling wave hands, knees soft, a broad smile. |
| `dance_twist` | 1.60 | loop | verified | in_place | - | Twist dance: knees bent, hips and shoulders counter-rotate, elbows pumping. |
| `clap` | 3.00 | once | verified | in_place | - | Applause: clapping briskly in front of the chest with a delighted grin. |
| `wave_hello` | 3.20 | once | verified | in_place | - | Friendly wave hello/goodbye with the right hand raised, fingers open, wrist swinging. |
| `nod_yes` | 2.00 | once | verified | in_place | - | Agreeing nod, two clear head nods with a small smile. |
| `shake_no` | 2.00 | once | verified | in_place | - | Disagreeing head shake, lips pressed down. |
| `look_curious` | 4.40 | once | verified | in_place | - | Curious peering: leans in with a tilted head, one brow up, eyes narrowed, hands hanging loose. |
| `look_up_sky` | 5.00 | once | verified | in_place | - | Tips his head far back to look up at the sky or the treetops, squinting; a slow turn as something passes. |
| `lounge_sit_back` | 12.00 | loop | verified | in_place | - | Lounging on the sand propped back on both hands, legs stretched out, face tilted to the sun with a contented half smile. |
| `lounge_recline` | 14.00 | loop | verified | in_place | - | Reclining on one elbow in the shade, one knee drawn up with a hand draped over it, idly watching the waves. |
| `play_toss_catch` | 3.20 | loop | verified | in_place | coconut | Playfully tossing a coconut up with the right hand and catching it with both, eyes following its arc. |
| `play_kick_sand` | 3.00 | once | verified | in_place | - | Kicking sand idly while he thinks: the right foot scuffs forward, sand flies, hands loose, a lopsided smile. |
| `play_flex_pose` | 4.00 | once | verified | in_place | - | Mock bodybuilder poses on the beach: a double-biceps flex, then a side pose, with a ridiculous grin. |
| `play_skip` | 0.87 | loop | verified | in_place 1.8 m/s | - | Light-hearted skipping along the beach (1.8 m/s): bouncy gait, arms swinging loosely, big grin. timeScale = speed / 1.8. |

## Clips in development

- `turn_fish_on_fire`: bones sink 52 mm below the ground plane
- `swim_crawl`: first pass: limbs read correctly but stroke timing, body roll and the kick are not tuned; a dry viewer shows the body below the water line
- `swim_breaststroke`: first pass: the frog kick amplitude and glide timing are not tuned
- `tread_water`: first pass: eggbeater legs are only roughly timed; the legs are not hidden below a surface in a dry viewer
