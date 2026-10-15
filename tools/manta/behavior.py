"""
Giant manta ray behaviour: the data the game should read, plus a headless simulation that checks the tuning.

  python3 tools/manta/behavior.py   # writes assets/manta/manta_behavior.json and assets/manta/behavior_report.json

The config is the source of truth. The simulation is a stand-in for the game's AI: it moves a few mantas over the
lagoon while a wandering player walks about, and it counts how often the player would SEE a manta and how often
each event fires. Nothing here touches the game. It only checks that the numbers give the intended rhythm.
"""
import json
import math
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.abspath(os.path.join(HERE, "..", "..", "assets", "manta"))

CONFIG = {
    "creature": "giant_manta",
    "wingspan_m": 6.0,
    "units": "metres, seconds",
    "frame": "Y-up in the game. The rig is in place; heading, speed and depth come from the game.",
    "depth_m": {"patrol_min": 6.0, "patrol_max": 14.0, "surface": 0.5, "breach_apex": 3.0},
    "speed_mps": {"patrol": 1.4, "curious": 0.9, "feed": 0.45, "flee": 4.0, "turn_rate_dps": 22.0},
    "ranges_m": {
        "notice": 90.0,               # visible from here (silhouette and shadow)
        "curious_enter": 32.0,        # investigates a slow player inside this distance
        "curious_orbit": [7.0, 10.0],
        "startle": 6.0,               # too close: bolts
        "spear_startle": 12.0,        # a speared or thrown object inside this bolts it
        "breach_player_min": 25.0,
        "breach_player_max": 80.0,
        "shadow_pass_min": 25.0,
        "shadow_pass_max": 60.0,
        "shadow_pass_height": 6.0,
    },
    "timers_s": {
        "patrol_leg": [25.0, 60.0],
        "curious_hold": [12.0, 20.0],
        "feed_hold": [20.0, 40.0],
        "flee_hold": 12.0,
        "shadow_pass": 9.0,
        "breach_total": 5.8,          # rise 3.0 s, hang 0.8 s, fall 2.0 s
    },
    "cooldowns_s": {
        "curious": 600.0,
        "shadow_pass": 240.0,
        "breach_per_manta": [240.0, 420.0],
        "breach_global": 90.0,        # at most one breach anywhere in the world in this window
        "feed_per_manta": 1200.0,
    },
    "rates_per_s_when_eligible": {    # chance per second that an eligible manta starts the event
        "breach": 1.0 / 40.0,         # player inside breach range and the manta's breach cooldown has elapsed
        "curious": 1.0 / 45.0,        # slow player inside curious_enter
        "shadow_pass": 1.0 / 90.0,    # player in shadow_pass range, manta on patrol
        "feed": 1.0 / 90.0,           # a bloom zone exists and the manta is on patrol
    },
    "clips": {
        "patrol_cruise": ["glide_cruise", "glide_gentle"],
        "turn": ["turn_left", "turn_right"],
        "curious": ["curious_approach"],
        "feed": ["feed_open"],
        "flee": ["startle_burst", "flap_power"],
        "breach": ["breach_rise", "breach_fall"],
    },
    "noticeability": {
        "silhouette": "pale underside and dark dorsal with wings held wide: reads at 90 m against both sand and deep water",
        "shadow": "a soft dark blob the size of the wingspan on the seabed while altitude is under 12 m, fading out by 20 m",
        "sound": "a wing-beat cue on every flap (every 2.4 s cruising, every 1.1 s powered), spatialised, audible to 60 m",
        "event_cues": "a splash and a ripple ring on breach; a brief whoosh when it bolts",
        "frequency_target": "a manta is in view (within 90 m) about a fifth of the time an explorer is in the lagoon; a breach about every 6 to 10 min per manta while explorers are around",
    },
    "integration": {
        "status": "spec only, not implemented in the game",
        "owner": "the local Claude Code session in the game repository",
        "steps": [
            "Replace the procedural manta mesh with assets/manta/Manta.glb (one skinned mesh, 13 bones, 10 clips).",
            "Drive the state machine above from the game's own world (depth, waypoints, player position, bloom zones).",
            "Keep the clips in place: apply the game's heading and speed to the root, never bake motion into a clip.",
            "Hook the event cues (splash, ripple, sound) to the breach and flee transitions.",
            "Tune the numbers in this file first, then copy them into the game's data.",
        ],
    },
}


class Manta:
    """One manta running the state machine. Positions are metres in a flat world; z is depth (negative)."""

    def __init__(self, rng, home, bloom_zones):
        self.rng = rng
        self.home = home
        self.pos = [home[0] + rng.uniform(-40, 40), home[1] + rng.uniform(-40, 40), -rng.uniform(8.0, 12.0)]
        self.state = "patrol"
        self.timer = 0.0
        self.waypoint = None
        self.bloom = bloom_zones
        self.cool = {"curious": 0.0, "shadow_pass": 0.0, "feed": 0.0,
                     "breach": rng.uniform(*CONFIG["cooldowns_s"]["breach_per_manta"])}
        self.speed = CONFIG["speed_mps"]["patrol"]
        self.breach_t = 0.0

    def _new_waypoint(self):
        """Patrol inside a 150 m disc around the manta's home reef, so it stays on the player's side of the lagoon."""
        ang = self.rng.uniform(0, 2 * math.pi)
        r = 150.0 * math.sqrt(self.rng.random())
        z = -self.rng.uniform(CONFIG["depth_m"]["patrol_min"], CONFIG["depth_m"]["patrol_max"])
        self.waypoint = (self.home[0] + r * math.cos(ang), self.home[1] + r * math.sin(ang), z)

    def _enter(self, state, speed, hold=0.0):
        self.state = state
        self.speed = speed
        self.timer = hold

    def step(self, dt, player, global_breach_ready):
        """Advance one tick. Returns 'breach' when a breach starts on this tick, else None."""
        for k in self.cool:
            self.cool[k] = max(0.0, self.cool[k] - dt)
        px, py, _ = player["pos"]
        dist = math.hypot(self.pos[0] - px, self.pos[1] - py)
        rng_cfg = CONFIG["ranges_m"]

        if self.state == "breach":
            self.breach_t += dt
            if self.breach_t >= CONFIG["timers_s"]["breach_total"]:
                self._enter("patrol", CONFIG["speed_mps"]["patrol"])
            return None

        if self.state == "flee":
            self.timer -= dt
            if self.timer <= 0.0:
                self._enter("patrol", CONFIG["speed_mps"]["patrol"])
            else:
                self._move_away(player, dt, CONFIG["speed_mps"]["flee"])
            return None

        if dist < rng_cfg["startle"] or player.get("spear_dist", 1e9) < rng_cfg["spear_startle"]:
            self._enter("flee", CONFIG["speed_mps"]["flee"], CONFIG["timers_s"]["flee_hold"])
            return None

        if self.state == "curious":
            self.timer -= dt
            self._orbit(player, dt)
            if self.timer <= 0.0 or player["speed"] > 4.0:
                self._enter("patrol", CONFIG["speed_mps"]["patrol"])
            return None

        if self.state == "feed":
            self.timer -= dt
            self._wander_bloom(dt)
            if self.timer <= 0.0:
                self._enter("patrol", CONFIG["speed_mps"]["patrol"])
            return None

        if self.state == "shadow_pass":
            self.timer -= dt
            target = (px, py, -rng_cfg["shadow_pass_height"])
            self._move_towards(target, dt, CONFIG["speed_mps"]["patrol"])
            if self.timer <= 0.0:
                self._enter("patrol", CONFIG["speed_mps"]["patrol"])
            return None

        # patrol: glide between waypoints, then roll for triggers
        if self.waypoint is None or math.dist(self.pos, self.waypoint) < 4.0:
            self._new_waypoint()
        self._move_towards(self.waypoint, dt, CONFIG["speed_mps"]["patrol"])

        rates = CONFIG["rates_per_s_when_eligible"]
        if (global_breach_ready and self.cool["breach"] <= 0.0
                and rng_cfg["breach_player_min"] < dist < rng_cfg["breach_player_max"]
                and self.rng.random() < rates["breach"] * dt):
            self.cool["breach"] = self.rng.uniform(*CONFIG["cooldowns_s"]["breach_per_manta"])
            self.state = "breach"
            self.breach_t = 0.0
            return "breach"
        if (self.cool["curious"] <= 0.0 and dist < rng_cfg["curious_enter"] and player["speed"] < 2.5
                and self.rng.random() < rates["curious"] * dt):
            self.cool["curious"] = CONFIG["cooldowns_s"]["curious"]
            self._enter("curious", CONFIG["speed_mps"]["curious"], self.rng.uniform(*CONFIG["timers_s"]["curious_hold"]))
        elif (self.cool["shadow_pass"] <= 0.0 and rng_cfg["shadow_pass_min"] < dist < rng_cfg["shadow_pass_max"]
              and self.rng.random() < rates["shadow_pass"] * dt):
            self.cool["shadow_pass"] = CONFIG["cooldowns_s"]["shadow_pass"]
            self._enter("shadow_pass", CONFIG["speed_mps"]["patrol"], CONFIG["timers_s"]["shadow_pass"])
        elif (self.bloom and self.cool["feed"] <= 0.0 and self.rng.random() < rates["feed"] * dt):
            self.cool["feed"] = CONFIG["cooldowns_s"]["feed_per_manta"]
            self._enter("feed", CONFIG["speed_mps"]["feed"], self.rng.uniform(*CONFIG["timers_s"]["feed_hold"]))
        return None

    def _move_towards(self, target, dt, speed):
        d = math.dist(self.pos, target)
        if d < 1e-6:
            return
        step = min(speed * dt, d)
        for i in range(3):
            self.pos[i] += (target[i] - self.pos[i]) / d * step

    def _move_away(self, player, dt, speed):
        ax, ay = self.pos[0] - player["pos"][0], self.pos[1] - player["pos"][1]
        self._move_towards((self.pos[0] + ax, self.pos[1] + ay, self.pos[2]), dt, speed)

    def _orbit(self, player, dt):
        lo, hi = CONFIG["ranges_m"]["curious_orbit"]
        px, py, _ = player["pos"]
        r = 0.5 * (lo + hi)
        ang = math.atan2(self.pos[1] - py, self.pos[0] - px) + (CONFIG["speed_mps"]["curious"] / r) * dt
        self._move_towards((px + r * math.cos(ang), py + r * math.sin(ang), -CONFIG["depth_m"]["patrol_min"]),
                           dt, CONFIG["speed_mps"]["curious"])

    def _wander_bloom(self, dt):
        cx, cy, rad = self.bloom[0]
        if math.hypot(self.pos[0] - cx, self.pos[1] - cy) > rad:
            self._move_towards((cx, cy, self.pos[2]), dt, CONFIG["speed_mps"]["feed"])
        else:
            ang = self.rng.uniform(0, 2 * math.pi) if self.rng.random() < dt else 0.0
            self._move_towards((self.pos[0] + math.cos(ang), self.pos[1] + math.sin(ang), self.pos[2]),
                               dt, CONFIG["speed_mps"]["feed"] * 0.5)


class Player:
    """Wanders the lagoon: mostly slow, sometimes a sprint, never far from the island centre."""

    def __init__(self, rng):
        self.rng = rng
        self.pos = [rng.uniform(-80, 80), rng.uniform(-80, 80), 0.0]
        self.heading = rng.uniform(0, 2 * math.pi)

    def step(self, dt):
        if self.rng.random() < dt / 20.0:
            self.heading += self.rng.uniform(-math.pi, math.pi)
        speed = 4.0 if self.rng.random() < 0.15 else 1.5
        self.pos[0] += math.cos(self.heading) * speed * dt
        self.pos[1] += math.sin(self.heading) * speed * dt
        if math.hypot(self.pos[0], self.pos[1]) > 200:
            self.heading = math.atan2(-self.pos[1], -self.pos[0])
        return {"pos": tuple(self.pos), "speed": speed}


def simulate(seed, hours=1.0, mantas=3, dt=0.1):
    rng = random.Random(seed)
    player = Player(rng)
    bloom = [(40.0, -30.0, 35.0)]
    herd = [Manta(rng, (rng.uniform(-120, 120), rng.uniform(-120, 120)), bloom) for _ in range(mantas)]
    counts = {"breach": 0, "curious": 0, "shadow_pass": 0, "feed": 0, "flee": 0}
    seen_ticks = total_ticks = 0
    in_breach_range_s = 0.0
    speeds = []
    last_breach_t = None
    min_gap = None
    t, end = 0.0, hours * 3600.0
    rb = CONFIG["ranges_m"]
    while t < end:
        p = player.step(dt)
        for m in herd:
            before = m.state
            d = math.dist(m.pos[:2], p["pos"][:2])
            if rb["breach_player_min"] < d < rb["breach_player_max"] and m.state == "patrol":
                in_breach_range_s += dt
            global_ready = last_breach_t is None or (t - last_breach_t) >= CONFIG["cooldowns_s"]["breach_global"]
            if m.step(dt, p, global_ready) == "breach":
                counts["breach"] += 1
                if last_breach_t is not None:
                    gap = t - last_breach_t
                    min_gap = gap if min_gap is None else min(min_gap, gap)
                last_breach_t = t
            if m.state != before and m.state in counts:
                counts[m.state] += 1
            if d < rb["notice"]:
                seen_ticks += 1
            total_ticks += 1
            speeds.append(m.speed)
        t += dt
    speeds.sort()
    out = {k: round(v / mantas / hours, 2) for k, v in counts.items()}
    # Breaches per manta per hour that a player spent in breach range (the rate the player can actually experience)
    out["breach_per_manta_hour_in_range"] = round(counts["breach"] / max(in_breach_range_s / 3600.0, 1e-9), 2)
    out["seen_fraction"] = round(seen_ticks / max(total_ticks, 1), 4)
    out["min_gap_between_breaches_s"] = round(min_gap, 1) if min_gap is not None else None
    out["speed_mps_p50"] = round(speeds[len(speeds) // 2], 2)
    out["speed_mps_max"] = round(speeds[-1], 2)
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    runs = [simulate(seed) for seed in range(20)]
    keys = ("breach", "curious", "shadow_pass", "feed", "flee", "breach_per_manta_hour_in_range", "seen_fraction",
            "speed_mps_p50")
    means = {k: round(sum(r[k] for r in runs) / len(runs), 3) for k in keys}
    gaps = [r["min_gap_between_breaches_s"] for r in runs if r["min_gap_between_breaches_s"] is not None]
    report = {
        "runs": len(runs),
        "hours_per_run": 1.0,
        "mantas_per_run": 3,
        "per_manta_per_hour_means": {k: means[k] for k in keys
                                     if k not in ("seen_fraction", "speed_mps_p50", "breach_per_manta_hour_in_range")},
        "breach_per_manta_hour_while_player_in_25_to_80m": means["breach_per_manta_hour_in_range"],
        "seen_fraction_mean": means["seen_fraction"],
        "speed_mps_p50_mean": means["speed_mps_p50"],
        "speed_mps_max_over_runs": max(r["speed_mps_max"] for r in runs),
        "min_gap_between_breaches_s_over_runs": min(gaps) if gaps else None,
        "breach_global_cooldown_s": CONFIG["cooldowns_s"]["breach_global"],
    }
    with open(os.path.join(OUT, "manta_behavior.json"), "w", encoding="utf8") as f:
        json.dump(CONFIG, f, indent=1)
    with open(os.path.join(OUT, "behavior_report.json"), "w", encoding="utf8") as f:
        json.dump(report, f, indent=1)
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
