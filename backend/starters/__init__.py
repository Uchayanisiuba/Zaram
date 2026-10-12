"""Tested starting points for the pages people ask for most.

Written 11 October 2026, after a Minecraft-style game was asked for across two
days and never played. The resident model (Qwen3.8-27B at 2.2 bits) wrote a
plausible 400-line voxel game every time, and every time something in it was
wrong in a way no load check sees: W, A, S and D all moved sideways, the player
drifted with no key held, `onGround` was never cleared, a loop lost its `++`.
Each fix rewrote the page and broke something else. A harness with the same
model gets further because it runs, looks and edits -- but a model at that
quantisation still has to invent a physics loop from nothing, and that is where
it fails.

So for the kinds of page that are hard to get right from scratch, Zaram keeps
a starting point that has been played: walked, jumped, dug into, built on. The
model is shown it and changes what the person asked for, as SEARCH/REPLACE
edits, rather than retyping 600 lines and re-deriving collision. The person can
still ask for something written from nothing; then no starting point is offered.

**Model-neutral.** A starting point is a page, not a prompt tuned to a model;
any model that can read code can build on it, and a stronger one simply needs
it less. `CLAUDE.md`: build for the set of models.

Each is an HTML file in this folder and an entry below. The matcher decides when
it is offered and is narrow on purpose: offering a voxel world to someone who
asked for a snake game would be worse than offering nothing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

HERE = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Starter:
    name: str
    #: One line for the model: what it already does, so it knows what to keep.
    does: str
    matcher: "re.Pattern[str]"
    #: What the model is told it may change, and what it must leave alone.
    change: str = "Change the SETTINGS block for sizes, speeds and colours, and change the title."
    keep: str = "Keep what works: the movement and the collision are tested. Do not rewrite them unless the person asked for that to change."
    #: A request that matches this is not offered this starting point: the page
    #: is 3D and a person who asked for a flat one should not be handed it.
    unless: Optional["re.Pattern[str]"] = None

    @property
    def path(self) -> Path:
        return HERE / f"{self.name}.html"

    def code(self) -> str:
        return self.path.read_text(encoding="utf-8")

    def offered_for(self, text: str) -> bool:
        if self.unless and self.unless.search(text):
            return False
        # A game named as someone's own is not a request for one. Measured 11
        # October 2026: "It is a screenshot of our racing game. Go ahead and
        # build the page." -- a follow-up about a studio site -- was handed the
        # racing starter and the site became a racing game.
        if not any(not _OWNED.search(text[: m.start()]) for m in self.matcher.finditer(text)):
            return False
        return self.path.is_file()


#: Words just before a game's name that make it somebody's own, or the subject
#: of a picture, rather than something being asked for: "our racing game", "my
#: Minecraft server", "a screenshot of the platformer". Read on the text right
#: before the match, within the same sentence.
_OWNED = re.compile(
    r"(?:\b(?:our|my|their|his|her|your|its)(?!\s+own\b)|\b(?:screenshot|picture|photo|image|video|clip) of(?: (?:a|an|the|our|my|their))?)"
    r"(?:\s+[\w-]+){0,2}\s*$",
    re.IGNORECASE,
)

#: Said plainly that the page is flat: the racing and platformer starting points are 3D.
_FLAT = re.compile(r"\b(?:2 ?d|two[- ]d(?:imensional)?|side[- ]?scroll\w*|top[- ]?down|isometric|text[- ]based)\b", re.IGNORECASE)

# Order is precedence: the first starting point that fits is the one offered. The
# voxel world comes first because "a Minecraft parkour map" is a block world
# before it is anything else; racing precedes the platformer because "a racing
# game with jumps" is a racing game.
STARTERS: Dict[str, Starter] = {
    s.name: s
    for s in (
        Starter(
            name="voxel-world",
            does=(
                "a first-person block world in three.js: procedural terrain with grass, dirt, stone, sand, "
                "water and trees; WASD, mouse look (pointer lock, or drag where that is refused), jump, sprint, "
                "swimming; collision against every block so the player never falls through; left click mines, "
                "right click places, 1-9 and the wheel choose from a hotbar; a block outline under the crosshair; "
                "a start and pause screen. Light: one draw call per chunk, no lights or shadows, pixel ratio 1."
            ),
            matcher=re.compile(
                r"\b(mine ?craft\w*|mincraft\w*|minecaft\w*|voxel\w*|blocky (?:world|game)|block (?:world|game|building)|"
                r"sandbox (?:3d|game)|cube world|craft(?:ing)? (?:game|sandbox))\b",
                re.IGNORECASE,
            ),
            change="Change the SETTINGS block for sizes and speeds, add blocks to BLOCKS and HOTBAR, and change the title.",
            keep="Keep what works: the collision, the movement and the mine-and-place code are tested. Do not rewrite them unless the person asked for that to change.",
        ),
        Starter(
            name="racing",
            does=(
                "a 3D arcade racer in three.js: a boxy car on a closed track made from a spline (the TRACK_POINTS list), "
                "with kerbs, a start line and checkpoint posts, trees and mountains; W or up accelerates, S or down brakes "
                "then reverses, A and D steer, with steering that needs speed and eases off flat out, and a little slide; "
                "grass slows the car instead of stopping it; a chase camera that widens its view with speed; a lap counts "
                "only when every checkpoint was passed in order, forwards, so reversing over the line gains nothing; lap "
                "time, best lap, a lap total, a wrong-way warning, R to restart, Esc or P to pause, a speed and fps readout, "
                "and a start screen that needs no pointer lock. Light: a few merged meshes, colours baked into the vertices, "
                "no lights or shadows, pixel ratio 1."
            ),
            matcher=re.compile(
                r"\b(?:"
                r"(?:rac(?:e|ing|eing|ng|in)|raicing)\s+(?:car\s+|kart\s+|3d\s+|arcade\s+)?(?:games?|sims?|simulat\w+)"
                r"|(?:3d\s+|arcade\s+|car\s+|kart\s+)?racers?"
                r"|(?:car|cars|driving|drift\w*|rally|go[- ]?kart|kart|f1|formula\s*1)\s+(?:racing|race|games?|sims?|simulat\w+)"
                r"|(?:go[- ]?)?karts?"
                r"|drive\s+(?:a\s+|the\s+|my\s+)?(?:car|kart)"
                r")\b",
                re.IGNORECASE,
            ),
            change=(
                "Change the SETTINGS block for speeds, grip, laps, colours and the camera; change TRACK_POINTS for a different "
                "track shape (keep the bends gentle and the loop from crossing itself); change the car in the CAR section; and change the title."
            ),
            keep=(
                "Keep what works: the car physics, the track and off-track detection, the checkpoint and lap logic and the "
                "camera are tested. Do not rewrite them unless the person asked for that to change."
            ),
            unless=_FLAT,
        ),
        Starter(
            name="platformer",
            does=(
                "a 3D third-person platformer in three.js: a boxy character on a course of platforms (the LEVEL list: gaps, "
                "heights, sizes, coins, checkpoints and a goal), including platforms that slide along x, y or z and carry the "
                "player; WASD moves relative to the camera, Space jumps (tap for a hop, hold for height, with coyote time and "
                "a jump buffer), fixed-step gravity, box collision that sets and clears onGround every step; an orbit camera "
                "turned by dragging the mouse or the arrow keys, wheel to zoom; coins with a counter, checkpoint flags, "
                "a fall below KILL_Y returns to the last checkpoint, a landing shadow, a goal flag that opens a win screen "
                "with time, coins and falls; R returns to the checkpoint, Esc or P pauses, an fps and position readout, and a "
                "start screen that needs no pointer lock. Light: a few merged meshes, colours baked into the vertices, no "
                "lights or shadows, pixel ratio 1."
            ),
            matcher=re.compile(
                r"\b(?:"
                r"platform(?:er|ers|ing)|plat[fh]?ormr|plaformer|platfromer|platfomer"
                r"|platform\s+(?:games?|adventures?)"
                r"|obstacle\s+(?:course|run)|obby|obbie|parkou?r|parcour"
                r"|(?:jump(?:ing)?|jumper)\s+(?:game|puzzle|course|map)|jump\s+and\s+run|run\s+and\s+jump"
                r"|mario[- ]?(?:like|style|clone|esque)|super\s+mario"
                r")\b",
                re.IGNORECASE,
            ),
            change=(
                "Change the SETTINGS block for speeds, jump, gravity and colours; change the LEVEL list to build a different "
                "course (each step is placed after the one before, so keep gap under 3.2 and up under 1.2 to stay jumpable); "
                "and change the title."
            ),
            keep=(
                "Keep what works: the movement, the jump, the collision and the moving-platform carrying are tested. Do not "
                "rewrite them unless the person asked for that to change."
            ),
            unless=_FLAT,
        ),
    )
}

#: Words that mean the person wants it written from nothing.
_FROM_SCRATCH = re.compile(
    r"\b(from scratch|from nothing|no template|without (?:a )?(?:template|starter)|don'?t use (?:a |the )?(?:template|starter))\b",
    re.IGNORECASE,
)


#: A site *about* the thing rather than the thing: "a website for my go-kart
#: track", "a landing page for our Minecraft server". Handing either a playable
#: game would be worse than offering nothing.
_A_SITE = re.compile(
    r"\b(?:web ?sites?|web ?pages?|landing ?pages?|home ?pages?|portfolio|online (?:shop|store)|"
    r"booking (?:page|site|form)|sign[- ]?up page)\b",
    re.IGNORECASE,
)


def starter_for(text: str) -> Optional[Starter]:
    """The starting point for a page request, or ``None``."""
    if not text or _FROM_SCRATCH.search(text) or _A_SITE.search(text):
        return None
    for starter in STARTERS.values():
        if starter.offered_for(text):
            return starter
    return None


def starter_guidance(starter: Starter) -> str:
    """What the model is told when a starting point is offered.

    The code goes first and the instruction last, the order every untrusted or
    long block in Zaram's prompts follows, so the last thing read is what to do.
    """
    fence = "`" * 3
    return (
        f"Zaram has a tested starting point for this request, called {starter.name}. It already works and has "
        f"been played: {starter.does}\n\n"
        f"{fence}html {starter.name}.html\n{starter.code()}\n{fence}\n\n"
        "Build on it rather than writing the page again:\n"
        f"- Start your reply with the line `Starting from: {starter.name}`.\n"
        "- Then write only what changes, as SEARCH/REPLACE blocks against the code above:\n"
        f"  {fence}\n  <<<<<<< SEARCH\n  lines copied exactly from the code above\n  =======\n  the lines that replace them\n"
        f"  >>>>>>> REPLACE\n  {fence}\n"
        "  Copy each SEARCH part character for character, keep each block small, and use as many blocks as you need. "
        f"{starter.change}\n"
        "- If it already does what was asked, the starting line alone is a complete reply; say in a sentence what it does.\n"
        f"- {starter.keep}\n"
        "- Never write the whole page out again; Zaram applies your changes to the starting point and shows the result."
    )
