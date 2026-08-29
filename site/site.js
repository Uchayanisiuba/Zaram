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
  formEndpoint: "",
  formHost:     "the form host",
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
    const response = await fetch(CONFIG.formEndpoint, {
      method: "POST",
      headers: { "Accept": "application/json", "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) throw new Error("HTTP " + response.status);
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

applyConfig();
$all('[data-role="signup"]').forEach(form => form.addEventListener("submit", submitSignup));
