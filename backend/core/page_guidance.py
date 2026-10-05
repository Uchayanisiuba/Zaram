"""What a model is told when it is asked for a page that runs in the browser.

Written 5 October 2026, from one page. The resident model wrote a
Minecraft-style "Block World" that could never be played, and every reason
was one any model could have avoided had it been told:

* it loaded `three@0.160.0/build/three.min.js` -- a file three.js stopped
  shipping in r160, so the page failed with the network on as well as off;
* its "click to start" listener was on the canvas, under a full-window overlay
  that took every click, so the start screen never cleared;
* its physics let a falling player pass through the ground.

The preview now serves three.js from Zaram's own copy
(`frontend/src/lib/previewLibraries.ts`), which fixes the first wherever the
page asked for it. These lines are for the rest: they ask for the shape that
works both in the preview, offline, and in the saved file opened in a browser.

**Sent only when the request is for a page** -- a game, a site, an HTML file.
Every other turn is unchanged, so the server's prompt cache keeps hitting for
them and nobody pays these tokens to be told about canvases.

**Model-neutral.** Nothing here names a model or is tuned to one; it is the
contract of the preview, stated. `CLAUDE.md`: build for the set of models.
"""

from __future__ import annotations

import re

#: Words that mean the reply will be a page somebody runs. Matched on the
#: request text only, as whole words.
_PAGE_WORDS = re.compile(
    r"\b(html|web ?page|website|web ?site|landing page|browser|game|three\.?js|webgl|canvas|"
    r"minecraft|platformer|shooter|snake|tetris|pong)\b",
    re.IGNORECASE,
)

PAGE_GUIDANCE = """\
When the answer is a page that runs in the browser:
- A small page is one ```html block — markup, CSS and script together — so it can be previewed and saved as one file.
- A larger app may be several files. Name each file on its fence line (```html index.html, ```css style.css, ```js game.js, ```js src/world.js), link them by relative path (`<link href="style.css">`, `<script type="module" src="game.js">`, `import { x } from './world.js'`), and write every file in full. Zaram runs them together and saves them as a folder; no project, terminal or install step is involved, so use only plain HTML, CSS and JavaScript. Anything the page reads at run time (data, levels, images) goes inside those files as code or a data: URL, because `fetch` and file loads are blocked.
- Zaram previews it with no network. three.js and these addons are served offline: controls/PointerLockControls, controls/OrbitControls, controls/FirstPersonControls, math/ImprovedNoise, math/SimplexNoise. Load them with an import map, which also works when the saved file is opened online:
  <script type="importmap">{"imports":{"three":"https://cdn.jsdelivr.net/npm/three/build/three.module.js","three/addons/":"https://cdn.jsdelivr.net/npm/three/examples/jsm/"}}</script>
  then `import * as THREE from 'three'` and `import { PointerLockControls } from 'three/addons/controls/PointerLockControls.js'` in a <script type="module">. Do not use build/three.min.js; it no longer exists. Any other library will not load in the preview.
- A start screen that covers the page takes the click itself: put the listener on the start screen (or the document), start the game and hide the screen in that handler. Request pointer lock from that click, and show the screen again when the lock is released.
- When asked to change a page you already wrote, reply with the whole updated page in one ```html block, never only the changed lines: the person runs the page, and a fragment cannot be run. For an app of several files, write every file again in full with its name.
- Before finishing, re-read every loop: each `for` must change its counter (`i++`), and nothing may run unbounded at start-up. A loop that never ends freezes the whole page before it draws anything.
- Draw the first screen (menu, title, "Loading…") before any heavy work, then do the work in small pieces across frames — a few chunks of a world per `requestAnimationFrame` or `setTimeout`, with a progress line — never as one loop that holds the page still for seconds. A page that is blank for ten seconds reads as broken.
- Keep a moving body out of solid ground: clamp each frame's time step, split a fast move into steps smaller than one block, and start the player standing on the surface rather than in the air above it.
"""


def wants_page_guidance(text: str, last_answer: str = "") -> bool:
    """Whether this request is for something that runs in a browser.

    Also true when the reply before it *was* a page: "the floor collision
    doesn't work" names no page, and it is a request to change one -- answered
    on 5 October 2026 with only the changed lines, which nobody can run.
    """
    return bool(_PAGE_WORDS.search(text or "")) or "```html" in (last_answer or "").lower()
