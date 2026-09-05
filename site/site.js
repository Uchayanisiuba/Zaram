/* Zaram site — the only file you edit to switch the page from waitlist to download.
   Everything below CONFIG is machinery; you should never need to touch it. */

const CONFIG = {

  // ── THE SWITCH ────────────────────────────────────────────────────────────
  // false → the waitlist form is the main call to action, download is hidden.
  // true  → the download button is the main call to action, waitlist moves to
  //         the bottom of the page as "notify me".
  // Flip this ONLY after you have installed the .exe on a machine that is not
  // your development machine. See site/README.md.
  releaseLive: false,

  // ── THE BUILD ─────────────────────────────────────────────────────────────
  // electron-builder.yml names the artifact Zaram-${version}-${arch}.exe, so the
  // version is part of the filename and the link is built from it below. Change
  // `version` and `sizeMb` when you cut a release; the URL follows.
  // sizeMb is MiB, matching what Windows Explorer shows the user — not decimal MB.
  // scripts/release-checksum.mjs prints the correct number for the built file.
  version: "0.1.0",
  sizeMb:  178,
  repo:    "Uchayanisiuba/Zaram",

  // Shown in the badge and echoed in the signup copy while releaseLive is false.
  // Keep it vague enough to be true: a date you miss is the first thing an alpha
  // tester learns about how reliable you are.
  firstBuild: "first builds in early September",

  // Paste the SHA-256 from the release page. Leave empty and the page says the
  // checksum is still pending, rather than showing a blank box.
  sha256: "",

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
      ? `Alpha · Windows · v${CONFIG.version}`
      : `Alpha · Windows · ${CONFIG.firstBuild}`;
  });

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
  { who: "You",   text: "Remember: the launch is 9 September in Lagos." },
  { who: "Zaram", text: "Noted — I'll remember that.", think: 620 },
  { who: "You",   text: "When is the launch?", pause: 900 },
  { who: "Zaram", text: "9 September, in Lagos.", cite: "M1",
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
