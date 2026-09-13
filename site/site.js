/* Zaram site — the only file you edit to switch the page from waitlist to download.
   Everything below CONFIG is machinery; you should never need to touch it. */

const CONFIG = {

  // ── THE SWITCH ────────────────────────────────────────────────────────────
  // false → the waitlist form is the main call to action, download is hidden.
  // true  → the download button is the main call to action, waitlist moves to
  //         the bottom of the page as "notify me".
  // Flip this ONLY after you have installed the .exe on a machine that is not
  // your development machine. See site/README.md.
  releaseLive: true,

  // ── THE BUILD ─────────────────────────────────────────────────────────────
  // electron-builder.yml names the artifact Zaram-${version}-${arch}.exe, so the
  // version is part of the filename and the link is built from it below. Change
  // `version` and `sizeMb` when you cut a release; the URL follows.
  // sizeMb is MiB, matching what Windows Explorer shows the user — not decimal MB.
  // scripts/release-checksum.mjs prints the correct number for the built file.
  version: "0.1.0",
  sizeMb:  198,
  repo:    "Uchayanisiuba/Zaram",

  // Shown in the badge and echoed in the signup copy while releaseLive is false.
  // Keep it vague enough to be true: a date you miss is the first thing an alpha
  // tester learns about how reliable you are.
  firstBuild: "first build 21 September",

  // The day the alpha opens. Shown beside the badge and in the download
  // note either way: before the switch it is when the build goes out, after
  // it is when the alpha programme — the feedback loop, the "what went
  // wrong" emails — starts for the people who install it.
  alphaOpens: "21 September",

  // Paste the SHA-256 from the release page. Leave empty and the page says the
  // checksum is still pending, rather than showing a blank box.
  sha256: "59e68a9802a0c4401db76771b7270f3c0b47dc30d6158dffed1e1ab7f9b056b0",

  // ── THE WAITLIST ──────────────────────────────────────────────────────────
  // Paste the endpoint from whichever form host you signed up with, and name it
  // so the footer can tell visitors truthfully where their address goes.
  // Leave endpoint empty and the form explains it isn't connected yet instead
  // of silently swallowing addresses.
  //
  //   formKind: "json"    Formspree and most form backends. POSTs JSON and
  //                       reads the reply, so a failure is a real failure and
  //                       the person is told. Recommended.
  //                       endpoint: https://formspree.io/f/xxxxxxxx
  //
  //   formKind: "google"  A Google Form. Free and uncapped, and the responses
  //                       land in a sheet you own — but the browser is not
  //                       allowed to read the reply, so the page cannot tell a
  //                       delivered address from a lost one and has to assume
  //                       it worked. On a product that refuses to overstate
  //                       what it knows, that is a real cost. Use it only if
  //                       the cap on the other one actually bites.
  //                       endpoint: https://docs.google.com/forms/d/e/FORM_ID/formResponse
  //                       and fill googleFields with the entry.NNN ids.
  formEndpoint: "https://formspree.io/f/mwlkpnej",
  formKind:     "json",
  formHost:     "Formspree",
  googleFields: { email: "", setup: "", intent: "" },
};

// ─────────────────────────────────────────────────────────────────────────────

const $all = (sel, root = document) => Array.from(root.querySelectorAll(sel));

/** The asset URL, assembled from the version so there is one field to change. */
function downloadUrl() {
  const { repo, version } = CONFIG;
  return `https://github.com/${repo}/releases/download/v${version}/Zaram-${version}-x64.exe`;
}

function applyConfig() {
  $all('[data-role="version"]').forEach(el => { el.textContent = CONFIG.version; });
  $all('[data-role="size"]').forEach(el => { el.textContent = String(CONFIG.sizeMb); });
  $all('[data-role="form-host"]').forEach(el => { el.textContent = CONFIG.formHost; });

  $all('[data-role="download-link"]').forEach(el => { el.href = downloadUrl(); });

  // A version number is meaningless until there is a file carrying it, so before
  // the build exists the badge states the timing instead.
  $all('[data-role="eyebrow"]').forEach(el => {
    el.textContent = CONFIG.releaseLive
      ? `Alpha · Windows · v${CONFIG.version} · opens ${CONFIG.alphaOpens}`
      : `Alpha · Windows · ${CONFIG.firstBuild}`;
  });
  $all('[data-role="alpha-date"]').forEach(el => { el.textContent = CONFIG.alphaOpens; });

  const waitlist = document.querySelector('[data-role="waitlist"]');
  const download = document.querySelector('[data-role="download"]');
  const closing  = document.querySelector('.closing');

  if (waitlist) waitlist.hidden = CONFIG.releaseLive;
  if (download) download.hidden = !CONFIG.releaseLive;
  // While there is nothing to download, one signup form is enough; once there is,
  // the closing "notify me" block earns its place again. Set both ways, so the
  // switch is symmetrical and flipping it back is not a one-way door.
  if (closing) closing.hidden = !CONFIG.releaseLive;

  const block   = document.querySelector('[data-role="checksum-block"]');
  const pending = document.querySelector('[data-role="checksum-pending"]');
  const digest  = document.querySelector('[data-role="sha256"]');
  if (CONFIG.sha256 && block && digest) {
    digest.textContent = CONFIG.sha256;
    block.hidden = false;
    if (pending) pending.hidden = true;
  }
}

function statusFor(form) {
  // Each form sits in a section that carries its own status line.
  const scope = form.closest('.cta, .closing') || document;
  return scope.querySelector('[data-role="signup-status"]');
}

function say(node, message, kind) {
  if (!node) return;
  node.textContent = message;
  node.className = "cta-status" + (kind ? " " + kind : "");
}

async function submitSignup(event) {
  event.preventDefault();
  const form   = event.currentTarget;
  const input  = form.querySelector('input[name="email"]');
  const button = form.querySelector("button");
  const status = statusFor(form);

  // Name the first empty required field rather than saying "check the form".
  const missing = Array.from(form.elements).find(
    (el) => el.willValidate && el.required && !el.checkValidity(),
  );
  if (missing) {
    const label = missing === input ? "That doesn't look like an email address."
                                    : "Pick an option for “What are you running?”";
    say(status, label, "err");
    missing.focus();
    return;
  }

  if (!CONFIG.formEndpoint) {
    // Better to admit this than to accept an address and drop it.
    say(status, "The form isn't connected yet — check back shortly.", "err");
    return;
  }

  // Send every field the form happens to carry, so the short form at the bottom
  // and the longer one at the top both work without a second code path.
  const payload = Object.fromEntries(new FormData(form).entries());

  const original = button.textContent;
  button.disabled = true;
  button.textContent = "Sending…";
  say(status, "", "");

  try {
    if (CONFIG.formKind === "google") {
      // A Google Form replies with headers the page is not permitted to read,
      // so this is send-and-hope by construction. Anything that throws is still
      // caught below; what cannot be detected is a 4xx from Google itself.
      const body = new URLSearchParams();
      for (const [field, entry] of Object.entries(CONFIG.googleFields)) {
        if (entry && payload[field]) body.append(entry, payload[field]);
      }
      await fetch(CONFIG.formEndpoint, { method: "POST", mode: "no-cors", body });
    } else {
      const response = await fetch(CONFIG.formEndpoint, {
        method: "POST",
        headers: { "Accept": "application/json", "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!response.ok) throw new Error("HTTP " + response.status);
    }
    form.reset();
    say(
      status,
      CONFIG.releaseLive
        ? "Done — you'll hear about the next build."
        : "You're in. I'll email you when the first build is ready.",
      "ok",
    );
    button.textContent = "Done";
  } catch (err) {
    say(status, "That didn't send. Try again, or open an issue on GitHub.", "err");
    button.disabled = false;
    button.textContent = original;
  }
}

/* ── The recall demo, replayed ───────────────────────────────────────────────
   Ask, be remembered, ask again, get a cited answer. It is the product's
   central claim and the one thing a screenshot cannot show.

   Three rules it obeys:
     - It plays ONCE, when scrolled into view, then rests on the final state.
       A loop becomes wallpaper and stops being read.
     - Reduced motion gets the finished exchange, already in the HTML,
       untouched. Opting out of motion must not opt you out of the content.
     - The user's line is typed by character and Zaram's is streamed by word,
       because that is what the two things actually do.                       */

const SCRIPT = [
  { who: "You",   text: "Remember: the launch is 9 September in Accra." },
  { who: "Zaram", text: "Noted — I'll remember that.", think: 620 },
  { who: "You",   text: "When is the launch?", pause: 900 },
  { who: "Zaram", text: "9 September, in Accra.", cite: "M1",
    src: "<b>M1</b> Memory · you told me this", think: 780 },
];

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function setWorking(on) {
  const stage = document.querySelector('[data-role="orb-stage"]');
  const demo = document.querySelector(".demo");
  const label = document.querySelector('[data-role="orb-state"]');
  const state = document.querySelector('[data-role="demo-state"]');
  if (stage) stage.classList.toggle("is-working", on);
  if (demo) demo.classList.toggle("is-working", on);
  // Working, never routing: the orb says what the system is doing and no more.
  if (label) label.textContent = on ? "Working — on this machine" : "Local only — nothing is sent out";
  if (state) state.textContent = on ? "Working · on this machine" : "Idle · on this machine";
}

async function writeInto(node, text, perChar) {
  const caret = document.createElement("span");
  caret.className = "caret";
  node.after(caret);
  for (let i = 0; i < text.length; i++) {
    node.textContent += text[i];
    await sleep(perChar);
  }
  caret.remove();
}

async function streamInto(node, text, perWord) {
  const caret = document.createElement("span");
  caret.className = "caret";
  node.after(caret);
  const words = text.split(" ");
  for (let i = 0; i < words.length; i++) {
    node.textContent += (i ? " " : "") + words[i];
    await sleep(perWord);
  }
  caret.remove();
}

let playing = false;

async function playDemo() {
  const thread = document.querySelector('[data-role="thread"]');
  const replay = document.querySelector('[data-role="replay"]');
  if (!thread || playing) return;
  playing = true;
  if (replay) replay.hidden = true;
  thread.textContent = "";
  setWorking(false);

  for (const step of SCRIPT) {
    if (step.pause) await sleep(step.pause);
    const zaram = step.who === "Zaram";

    if (zaram) {
      setWorking(true);
      await sleep(step.think || 500);
    }

    const turn = document.createElement("div");
    turn.className = "turn" + (zaram ? " is-zaram" : "");
    const who = document.createElement("span");
    who.className = "speaker";
    who.textContent = step.who;
    const p = document.createElement("p");
    turn.append(who, p);
    thread.append(turn);

    if (zaram) {
      await streamInto(p, step.text, 90);
      if (step.cite) {
        const c = document.createElement("span");
        c.className = "cite";
        c.textContent = step.cite;
        p.append(" ", c);
      }
      if (step.src) {
        await sleep(260);
        const s = document.createElement("p");
        s.className = "src";
        s.innerHTML = step.src;
        turn.append(s);
      }
      await sleep(220);
      setWorking(false);
    } else {
      await writeInto(p, step.text, 26);
      await sleep(320);
    }
  }

  playing = false;
  if (replay) replay.hidden = false;
}

function armDemo() {
  const demo = document.querySelector(".demo");
  if (!demo) return;
  // The written-out exchange stays exactly as it is for anyone who asked for
  // less motion — there is nothing to arm.
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

  const replay = document.querySelector('[data-role="replay"]');
  if (replay) replay.addEventListener("click", playDemo);

  if (!("IntersectionObserver" in window)) { playDemo(); return; }
  const io = new IntersectionObserver((entries) => {
    for (const e of entries) {
      if (e.isIntersecting) { io.disconnect(); playDemo(); }
    }
  }, { threshold: 0.35 });
  io.observe(demo);
}

applyConfig();
$all('[data-role="signup"]').forEach(form => form.addEventListener("submit", submitSignup));
armDemo();

/* ---------------------------------------------------------------------------
   Depth. The scene's layers follow the pointer and the scroll; the cards
   lean toward the pointer; things below the fold rise as they arrive.

   All of it is decoration, and it obeys the one rule the product itself
   keeps: motion has a budget. Nothing here runs under
   prefers-reduced-motion, nothing runs while the scene is off screen, the
   whole thing is a handful of CSS variables set once per frame, and a page
   without this script is the same page standing still.
   ------------------------------------------------------------------------ */

const MOTION_OK = !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const FINE_POINTER = window.matchMedia("(hover: hover) and (pointer: fine)").matches;

/** Where the pointer is, −1..1 either way, and how far the page has gone.
    Eased toward the target so the layers glide rather than snap. */
function armScene() {
  const scene = document.querySelector('[data-role="scene"]');
  if (!scene || !MOTION_OK) return;

  const hero = scene.closest(".embodiment, .hero") || document.body;
  let tx = 0, ty = 0, mx = 0, my = 0, sy = 0, visible = true, raf = 0;

  if (FINE_POINTER) {
    hero.addEventListener("pointermove", (e) => {
      const r = scene.getBoundingClientRect();
      tx = Math.max(-1, Math.min(1, ((e.clientX - r.left) / r.width - 0.5) * 2));
      ty = Math.max(-1, Math.min(1, ((e.clientY - r.top) / r.height - 0.5) * 2));
    }, { passive: true });
    hero.addEventListener("pointerleave", () => { tx = 0; ty = 0; });
  }
  // Scroll is measured as where the scene sits relative to the middle of the
  // viewport, not as the page's scroll offset: the layers shift as the scene
  // passes through view and are back in place when it is centred, wherever
  // on the page it lives.
  const measure = () => {
    const r = scene.getBoundingClientRect();
    sy = Math.max(-600, Math.min(600, (r.top + r.height / 2) - window.innerHeight / 2));
  };
  window.addEventListener("scroll", measure, { passive: true });
  window.addEventListener("resize", measure, { passive: true });
  measure();

  if ("IntersectionObserver" in window) {
    new IntersectionObserver((entries) => {
      visible = entries.some((e) => e.isIntersecting);
      if (visible && !raf) tick();
    }, { rootMargin: "120px" }).observe(scene);
  }

  const stars = armStars(scene.querySelector('[data-role="stars"]'));
  const face = armFace(scene.querySelector('[data-role="avatar-face"]'), scene.querySelector('[data-role="avatar-img"]'));
  const stage = scene.querySelector('[data-role="orb-stage"]');

  function tick() {
    raf = 0;
    mx += (tx - mx) * 0.07;
    my += (ty - my) * 0.07;
    scene.style.setProperty("--mx", mx.toFixed(4));
    scene.style.setProperty("--my", my.toFixed(4));
    scene.style.setProperty("--sy", sy.toFixed(1));
    if (stars) stars(mx, my);
    if (face) face(mx, my, !!(stage && stage.classList.contains("is-working")));
    if (visible && !document.hidden) raf = requestAnimationFrame(tick);
  }
  document.addEventListener("visibilitychange", () => { if (!document.hidden && visible && !raf) tick(); });
  tick();
}

/** The character's face, drawn live on the visor.
 *
 *  The product's face is a dot-matrix display driven by texture cells; this
 *  is the same face in the same grid, drawn on a canvas over a render whose
 *  visor is blank. It does three things the still cannot: the eyes look
 *  toward the pointer (attention, not drift — the head already leans the
 *  same way), it blinks now and then, and while the demo is working the eyes
 *  become the thinking pattern the app uses. The rest face is the flat line,
 *  as in the product: a mascot may smile on the site, but this is the
 *  embodiment and it reports state.
 *
 *  Geometry is measured from the render (900×981): two 8×10 dot blocks and
 *  a 13-dot line, 12 px pitch, on a head turned a few degrees so the right
 *  eye sits a little lower. Returns the per-frame draw, or null. */
function armFace(canvas, img) {
  if (!canvas || !img) return null;
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;

  // Swap in the blank-visor render; if it fails to load, keep the still.
  const blank = new Image();
  blank.decoding = "async";
  blank.onload = () => { img.src = "img/avatar-blank.webp"; canvas.hidden = false; };
  blank.src = "img/avatar-blank.webp";

  const PITCH = 12, R = 4.6;
  const LEFT = { x: 316, y: 249 };      // top-left dot centres
  const RIGHT = { x: 522, y: 260 };
  const MOUTH = { x: 385, y: 461, n: 13 };
  const COLS = 8, ROWS = 10;
  const COLOUR = "196,205,255";

  let blinkAt = performance.now() + 2600 + Math.random() * 3000;
  let blinking = 0;                    // 0 open … 1 shut
  let t0 = performance.now();

  function dot(x, y, a, r = R) {
    ctx.fillStyle = `rgba(${COLOUR},${a})`;
    ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill();
  }

  /** One eye: a rounded block of dots, shifted toward the gaze, its rows
   *  collapsing toward the middle on a blink. */
  function eye(origin, gx, gy, shut, now, thinking) {
    const dx = Math.round(gx * 1.6), dy = Math.round(gy * 1.2);   // in dots
    const open = Math.max(1, Math.round(ROWS * (1 - shut)));
    const top = Math.floor((ROWS - open) / 2);
    for (let c = 0; c < COLS; c++) {
      for (let r = 0; r < ROWS; r++) {
        // rounded corners: skip the four corner dots
        const corner = (c === 0 || c === COLS - 1) && (r === 0 || r === ROWS - 1);
        if (corner) continue;
        if (r < top || r >= top + open) continue;
        let a = 0.92;
        if (thinking) {
          // a soft wave travelling across the block, the app's "working" face
          const phase = (now - t0) / 380 - c * 0.55 - r * 0.12;
          a = 0.28 + 0.62 * (0.5 + 0.5 * Math.sin(phase));
        }
        dot(origin.x + (c + dx) * PITCH, origin.y + (r + dy) * PITCH, a);
      }
    }
  }

  return function draw(mx, my, thinking) {
    const now = performance.now();
    if (now > blinkAt) {
      const k = (now - blinkAt) / 140;               // 140 ms down, 140 up
      blinking = k < 1 ? k : k < 2 ? 2 - k : 0;
      if (k >= 2) { blinkAt = now + 2600 + Math.random() * 4200; blinking = 0; }
    }
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.shadowColor = `rgba(${COLOUR},0.55)`; ctx.shadowBlur = 6;
    eye(LEFT, mx, my, blinking, now, thinking);
    eye(RIGHT, mx, my, blinking, now, thinking);
    // the mouth: the flat line at rest; a slightly wider one while thinking
    const n = thinking ? MOUTH.n - 2 : MOUTH.n;
    const x0 = MOUTH.x + ((MOUTH.n - n) / 2) * PITCH;
    for (let i = 0; i < n; i++) dot(x0 + i * PITCH, MOUTH.y, 0.85, R - 0.6);
  };
}

/** A field of slow points with depth, on a canvas. About a hundred and
    forty of them, drifting toward the viewer, shifted by the pointer so the
    near ones move more than the far ones. Returns the per-frame draw. */
function armStars(canvas) {
  if (!canvas) return null;
  const ctx = canvas.getContext("2d", { alpha: true });
  if (!ctx) return null;

  const N = 140;
  const pts = [];
  let w = 0, h = 0, dpr = 1;

  function size() {
    const r = canvas.getBoundingClientRect();
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    w = Math.max(1, Math.round(r.width)); h = Math.max(1, Math.round(r.height));
    canvas.width = w * dpr; canvas.height = h * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  function seed(p) {
    p.x = Math.random() * 2 - 1; p.y = Math.random() * 2 - 1;
    p.z = Math.random() * 0.9 + 0.1;              // 0.1 far … 1 near
    p.c = Math.random() < 0.72 ? "94,231,220" : "139,127,212";
    return p;
  }
  size();
  for (let i = 0; i < N; i++) pts.push(seed({}));
  window.addEventListener("resize", size, { passive: true });

  return function draw(mx, my) {
    ctx.clearRect(0, 0, w, h);
    const cx = w / 2, cy = h / 2;
    for (const p of pts) {
      p.z += 0.0011;                              // drift toward the viewer
      if (p.z > 1.15) seed(p), (p.z = 0.1);
      const k = 0.55 / p.z;                       // perspective
      const x = cx + (p.x + mx * 0.08 * p.z) * cx * k;
      const y = cy + (p.y + my * 0.06 * p.z) * cy * k;
      if (x < -4 || x > w + 4 || y < -4 || y > h + 4) continue;
      const a = Math.min(1, (p.z - 0.1) * 1.4) * 0.75;
      const s = 0.6 + p.z * 1.6;
      ctx.fillStyle = `rgba(${p.c},${a.toFixed(3)})`;
      ctx.beginPath(); ctx.arc(x, y, s, 0, Math.PI * 2); ctx.fill();
    }
  };
}

/** Cards lean toward the pointer, a few degrees, and a glare follows it. */
function armTilt() {
  if (!MOTION_OK || !FINE_POINTER) return;
  const cards = $all(".claims > div, .caps-grid > div, .who-row, main .panel:not(.demo)");
  for (const el of cards) {
    el.classList.add("tilt");
    el.addEventListener("pointermove", (e) => {
      const r = el.getBoundingClientRect();
      const px = (e.clientX - r.left) / r.width, py = (e.clientY - r.top) / r.height;
      const max = r.width > 700 ? 3 : 6;         // wide panels lean less
      el.style.setProperty("--ry", `${((px - 0.5) * 2 * max).toFixed(2)}deg`);
      el.style.setProperty("--rx", `${((0.5 - py) * 2 * max).toFixed(2)}deg`);
      el.style.setProperty("--gx", `${(px * 100).toFixed(1)}%`);
      el.style.setProperty("--gy", `${(py * 100).toFixed(1)}%`);
      el.classList.add("is-live");
    }, { passive: true });
    el.addEventListener("pointerleave", () => {
      el.style.setProperty("--rx", "0deg"); el.style.setProperty("--ry", "0deg");
      el.classList.remove("is-live");
    });
  }
}

/** Below the fold, things arrive as they are reached. */
function armReveal() {
  if (!MOTION_OK || !("IntersectionObserver" in window)) return;
  const targets = $all("main section:not(.hero) .feature-text, main section:not(.hero) .panel, .claims > div, .caps-grid > div, .who-row, .policy-list li, .honest-grid > div");
  const io = new IntersectionObserver((entries) => {
    for (const e of entries) if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); }
  }, { threshold: 0.12, rootMargin: "0px 0px -6% 0px" });
  targets.forEach((el, i) => {
    el.classList.add("reveal");
    el.style.transitionDelay = `${(i % 3) * 60}ms`;
    io.observe(el);
  });
}

armScene();
armTilt();
armReveal();
