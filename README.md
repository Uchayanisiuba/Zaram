# The Zaram site

A static page. Three files, no build step, no dependencies, no framework. Open
`index.html` in a browser and it works.

It makes **no third-party requests on load** — no fonts, no analytics, no CDN.
The only outbound request it can ever make is the one carrying an email address
to your form host, and only when someone presses the button. That is deliberate:
a page selling "nothing leaves the device" should not itself phone four
companies to render.

```
site/
  index.html     the page
  styles.css     palette from docs/UI-SPEC.md, so site and product agree
  site.js        CONFIG at the top is the only thing you edit
  favicon.ico    copied from build/icon.ico
  img/           screenshots, downscaled to webp (130 KB for all five)
```

---

## Publishing it, free

The site must live in **its own public repo**, not in the Zaram repo. GitHub
Pages can only serve from a repo root or a `/docs` folder, and `docs/` here holds
MILESTONES, KNOWN-FAILURES, HANDOVER and PITCH — internal notes and investor
framing that should not be one URL away from the landing page.

From the repo root:

```bash
git subtree split --prefix site -b site-only
```

Create an empty public repo called `zaram-site` on GitHub, then:

```bash
git push git@github.com:Uchayanisiuba/zaram-site.git site-only:main
```

In that new repo: **Settings → Pages → Source: Deploy from a branch → `main` /
(root)**. It is live at `https://uchayanisiuba.github.io/zaram-site/` in about a
minute. Nothing to pay, nothing to configure, HTTPS included.

To update later, repeat the subtree split and push. (Delete the local
`site-only` branch first: `git branch -D site-only`.)

### A custom domain, when you want one

Buy the domain anywhere (~$10–15/year, the only cost in this whole setup). Add a
file called `CNAME` to the site repo root containing just the domain, point the
domain's DNS at GitHub Pages, then tick **Enforce HTTPS**. The certificate is
free and automatic. Do this whenever — a domain swap is DNS, not a rebuild.

---

## The switch

`site.js` opens with a `CONFIG` block. It is the only part you edit.

| Field | What it does |
|---|---|
| `releaseLive` | `false` → waitlist is the main call to action, download hidden. `true` → download is the main call to action, waitlist moves to the bottom. |
| `version` | Drives the button label **and the download URL**. The installer is named `Zaram-${version}-x64.exe`, so changing this here is enough. |
| `sizeMb` | MiB, as Windows Explorer reports it. |
| `sha256` | Empty → the page says the checksum is pending. Set → the verification box appears. |
| `formEndpoint` | Empty → the form tells people it isn't connected instead of silently eating addresses. |
| `formHost` | Named in the footer, so visitors are told truthfully where their address goes. |

The switch is symmetrical: flipping it back restores the waitlist exactly. Both
states are wired and both have been exercised in a browser.

### Connecting the waitlist

Pick one and paste its endpoint into `formEndpoint`:

- **Tally** — free, 100 submissions/month, unlimited forms. The most headroom.
- **Formspree** — free, 50 submissions/month. Fine to start, tight if a post lands well.
- **Buttondown** — an actual newsletter tool, so you can email the list later
  without exporting anything. This is the one to want if the list is the point.

Whichever you choose, put its name in `formHost` so the footer stays true.

### Turning the download on

In order, and the first step is not optional:

1. `npm run build:desktop`
2. **Install the resulting `.exe` on a machine that is not your development
   machine.** A Windows VM counts. This is the step that catches the failure
   that only fires where Ollama was never running and no model is present.
3. `node scripts/release-checksum.mjs` — prints the digest and the exact lines
   to paste.
4. Create a GitHub release tagged `v0.1.0` on the Zaram repo, attach the `.exe`,
   put the checksum in the notes.
5. Paste `version`, `sizeMb` and `sha256` into `CONFIG`, set `releaseLive: true`,
   push the site.

Serve the binary from **GitHub Releases, never from Pages**. Pages has a 1 GB
size cap and a 100 GB/month soft bandwidth limit; at 178 MB a download that is
roughly 570 installs before GitHub emails you. Release asset traffic is counted
separately — GitHub's own limits page names releases as the mitigation.

---

## The signing gate

`npm run check:signing` **fails a release build that is unsigned**, by design, and
the reasoning is in the header of `scripts/check-signing.mjs`. It only fires when
`ZARAM_RELEASE=1`, so a development build stays unsigned and that is correct.

That gate is why the site ships waitlist-first. When you publish an unsigned
alpha anyway, you are choosing to, and the `#install` section on the page says so
in plain words rather than hoping nobody reads the SmartScreen dialog. Update
that section the day a certificate lands.
