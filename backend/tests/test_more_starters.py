"""The racing and platformer starting points: which requests get them, and what they carry.

11 October 2026, after the voxel world, for the same reason: a local 2.2-bit model
cannot write a first-person or third-person game that plays from nothing. Each of
these pages was *played* before it was committed -- driven in headless Chrome with
key presses and read back through `window.__game` -- and the measurements are in the
session notes, not asserted here, because a unit test cannot press a key. What a
test can hold is the contract around the files: who is offered them, that they stay
self-contained and light, and that no loop in them can freeze the page.
"""

from __future__ import annotations

import re

import pytest

from starters import STARTERS, starter_for, starter_guidance

NEW = ("racing", "platformer")


# -------------------------------------------------------------- who is offered


@pytest.mark.parametrize("text", [
    "make a racing game",
    "Create a 3D car racing game that I can play in my browser",
    "build me a kart racer in three.js",
    "a driving game with a chase camera",
    "write a raceing game in html",
    "a simple race car game",
    "build a rally game",
    "mario kart clone",
    "drive a car around a track in 3d",
    "arcade racer with laps",
])
def test_a_racing_request_is_offered_the_racing_starting_point(text):
    assert starter_for(text) is STARTERS["racing"], text


@pytest.mark.parametrize("text", [
    "make a 3D platformer",
    "create a platformer with coins and moving platforms",
    "a roblox style obby",
    "an obstacle course I can run through",
    "build a parkour game",
    "a mario-like 3d game",
    "a simple jump game in the browser",
    "a plaformer game",
])
def test_a_platformer_request_is_offered_the_platformer_starting_point(text):
    assert starter_for(text) is STARTERS["platformer"], text


@pytest.mark.parametrize("text", [
    "fix the race condition in my code",
    "a human race essay",
    "a website for car rental",
    "a landing page for my racing team",
    "build the car dealership page",
    "cart checkout page",
    "platform engineering roadmap",
    "an e-commerce platform for shoes",
    "write about the platform strategy of Apple",
    "make a snake game",
    "tracer round of the tests",
])
def test_everything_else_is_offered_neither(text):
    got = starter_for(text)
    assert got is None or got.name not in NEW, text


def test_a_request_that_says_it_is_flat_gets_no_3d_starting_point():
    for text in ("make a 2D racing game", "a 2d platformer", "a top-down racer", "a side scrolling platformer", "an isometric parkour game"):
        assert starter_for(text) is None, text


def test_a_site_about_the_thing_is_not_handed_a_game():
    for text in (
        "build a website for my go-kart track",
        "a landing page for our Minecraft server",
        "make a homepage for my parkour gym",
        "a booking page for the kart circuit",
    ):
        assert starter_for(text) is None, text
    # The game itself is still offered.
    assert starter_for("make a go-kart racing game").name == "racing"


def test_a_game_named_as_someones_own_is_not_a_request_for_one():
    # Measured 11 October 2026: a follow-up about a studio site, "It is a
    # screenshot of our racing game", was handed the racing starter.
    for text in (
        "It is a screenshot of our racing game. Go ahead and build the page.",
        "a hero image showing my platformer",
        "here is a picture of the minecraft map I made",
    ):
        assert starter_for(text) is None, text
    # Asking for one, including "my own", still gets it.
    assert starter_for("build me my own racing game").name == "racing"
    assert starter_for("make a minecraft game for my son").name == "voxel-world"


def test_from_scratch_is_honoured_for_both():
    for text in ("build a racing game from scratch", "make a platformer without a template", "a parkour game, no template"):
        assert starter_for(text) is None, text


def test_precedence_is_voxel_then_racing_then_platformer():
    assert list(STARTERS)[:3] == ["voxel-world", "racing", "platformer"]
    assert starter_for("minecraft racing") is STARTERS["voxel-world"]
    assert starter_for("a minecraft parkour map") is STARTERS["voxel-world"]
    assert starter_for("a racing game with jumps and an obstacle course") is STARTERS["racing"]
    assert starter_for("a 3d platformer where you drive a car between islands") is STARTERS["racing"]


def test_a_voxel_request_is_unchanged_by_the_new_matchers():
    for text in ("Build a Minecraft-style game", "make a voxel sandbox", "Creaye a Mine craft game"):
        assert starter_for(text) is STARTERS["voxel-world"], text


# --------------------------------------------------------------- what they are


@pytest.mark.parametrize("name", NEW)
def test_the_file_exists_and_is_small_enough_to_put_in_a_prompt(name):
    code = STARTERS[name].code()
    assert STARTERS[name].path.is_file()
    assert len(code.encode("utf-8")) < 30_000, "a starting point is read whole by the model on every request"


@pytest.mark.parametrize("name", NEW)
def test_it_has_a_settings_block_the_model_edits(name):
    code = STARTERS[name].code()
    assert re.search(r"//\s*-+\s*SETTINGS\b", code)
    settings = code.split("SETTINGS", 2)[-1].split("// ----", 1)[0]
    assert len(re.findall(r"\bconst\s+[A-Z_]+\b", settings)) >= 8


@pytest.mark.parametrize("name", NEW)
def test_the_import_map_is_the_one_the_preview_serves_offline(name):
    code = STARTERS[name].code()
    assert ('<script type="importmap">{"imports":{"three":"https://cdn.jsdelivr.net/npm/three@0.170.0/build/three.module.js"}}</script>'
            in code)
    assert code.count("importmap") == 1


@pytest.mark.parametrize("name", NEW)
def test_nothing_is_loaded_from_anywhere_but_the_import_map(name):
    code = STARTERS[name].code()
    urls = re.findall(r"https?://[^\s\"'<>)]+", code)
    assert urls and all(u.startswith("https://cdn.jsdelivr.net/npm/three@0.170.0/") for u in urls), urls
    assert not re.search(r"\bfetch\s*\(|XMLHttpRequest|@import|<link\b|\bsrc\s*=\s*[\"']http|WebSocket|sendBeacon", code)
    assert not re.search(r"font-family:[^;]*url\(", code)


@pytest.mark.parametrize("name", NEW)
def test_it_is_light_enough_to_run_beside_a_local_model(name):
    code = STARTERS[name].code()
    assert "renderer.setPixelRatio(1)" in code
    assert "antialias: false" in code
    assert not re.search(r"new THREE\.\w*Light\b|castShadow|shadowMap|MeshStandardMaterial|MeshPhongMaterial|MeshLambertMaterial|MeshPhysicalMaterial", code)
    assert "devicePixelRatio" not in code


@pytest.mark.parametrize("name", NEW)
def test_every_for_loop_has_an_increment(name):
    # The failure that froze a page for a person: `for (let z = a; z <= b; z)`.
    code = STARTERS[name].code()
    loops = re.findall(r"\bfor\s*\(([^()]*(?:\([^()]*\)[^()]*)*)\)", code)
    assert loops
    for header in loops:
        if " of " in header or " in " in header:
            continue
        parts = header.split(";")
        assert len(parts) == 3, header
        assert parts[2].strip(), f"a for loop with no increment: for ({header})"
        assert re.search(r"\+\+|--|\+=|-=|=", parts[2]), header


@pytest.mark.parametrize("name", NEW)
def test_it_starts_without_waiting_for_pointer_lock(name):
    code = STARTERS[name].code()
    start = code.split("function start()")[1].split("\nfunction ")[0]
    assert "playing = true" in start.split("requestPointerLock")[0]


@pytest.mark.parametrize("name", NEW)
def test_the_game_can_be_read_back_but_not_driven_through_its_debug_object(name):
    code = STARTERS[name].code()
    assert "Object.defineProperty(window, '__game'" in code and "Object.freeze" in code
    block = code.split("Object.defineProperty(window, '__game'")[1].split("// ---", 1)[0]
    assert not re.search(r"\bset\s+\w+\s*\(|=>\s*\{[^}]*\b(?:x|z|speed|pos)\s*=[^=]", block)


def test_the_racing_laps_cannot_be_gained_by_reversing_over_the_line():
    code = STARTERS["racing"].code()
    assert "function forwardGate" in code and "function backGate" in code
    # A lap completes only when every gate was passed, in order, and the line is then crossed forwards.
    assert "race.nextGate === GATES" in code and "k === race.nextGate" in code
    # And a back-crossing takes a gate away, so a gate cannot be banked by driving over it twice.
    assert "race.nextGate = k" in code


def test_the_platformer_collision_sets_and_clears_the_ground_every_step():
    code = STARTERS["platformer"].code()
    assert "P.onGround = false; P.ground = -1;" in code
    assert "P.onGround = true; P.ground = i;" in code
    assert "COYOTE_TIME" in code and "KILL_Y" in code and "function respawn" in code
    # Fixed steps, so a slow frame cannot become a long fall through a platform.
    assert "const STEP = 1 / 240" in code and "while (acc >= STEP)" in code


@pytest.mark.parametrize("name", NEW)
def test_nothing_is_allocated_inside_the_frame_loop(name):
    code = STARTERS[name].code()
    frame = code.split("function frame(now)")[1].split("\n}\n")[0]
    assert not re.search(r"\bnew\s+THREE\.|\bnew\s+(?:Array|Map|Set|Float32Array)\b|\.map\(|\.filter\(|\.slice\(|\[\.\.\.", frame)


# ----------------------------------------------------------------- the model


@pytest.mark.parametrize("name", NEW)
def test_the_model_is_told_to_edit_this_starting_point_and_not_the_voxel_one(name):
    text = starter_guidance(STARTERS[name])
    assert f"Starting from: {name}" in text
    assert "SEARCH/REPLACE" in text
    assert "BLOCKS" not in text and "HOTBAR" not in text and "mine-and-place" not in text
    assert text.rstrip().endswith("shows the result.")
    code_at = text.index("<script type=\"module\">")
    assert text.index(f"Starting from: {name}") > code_at, "the code goes first and the instruction last"


def test_what_the_voxel_guidance_says_is_unchanged():
    text = starter_guidance(STARTERS["voxel-world"])
    assert "add blocks to BLOCKS and HOTBAR" in text
    assert "mine-and-place code are tested" in text


def test_the_description_names_what_each_one_actually_has():
    racing, plat = STARTERS["racing"].does, STARTERS["platformer"].does
    for word in ("TRACK_POINTS", "checkpoint", "lap", "grass"):
        assert word in racing, word
    for word in ("LEVEL", "coyote", "KILL_Y", "checkpoint", "goal", "onGround"):
        assert word in plat, word
    # No model is named: a starting point is a page, not a prompt tuned to one.
    assert not re.search(r"qwen|gemma|llama|claude|gpt|mistral", racing + plat, re.IGNORECASE)


def test_the_window_can_fetch_each_starting_point_by_name():
    import main
    from fastapi.testclient import TestClient

    from core.api_secret import api_secret

    client = TestClient(main.app, headers={"X-Zaram-Auth": api_secret() or ""})
    for name in NEW:
        ok = client.get(f"/starters/{name}")
        assert ok.status_code == 200 and ok.json()["code"] == STARTERS[name].code()
