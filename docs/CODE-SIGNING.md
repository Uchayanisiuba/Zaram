# Code signing

**Status: not started. This is the longest-lead item on the road to alpha, and
the only one that cannot be compressed later.** Everything in the repo is ready
for a certificate; nothing can proceed without one, and obtaining one is
paperwork and waiting rather than work.

---

## What this is, and who it applies to

Windows checks whether an executable carries a signature from a certificate
authority vouching for who published it. Unsigned, SmartScreen shows a
full-screen *"Windows protected your PC"* warning and the user must click
**More info → Run anyway**.

For most software that is friction. For Zaram it is a contradiction. The
product's claim is that your documents stay yours and you can see exactly what
leaves — and the first thing a new user meets is Windows saying it cannot
vouch for the publisher. It also trains precisely the reflex the product needs
intact: clicking through a security warning without reading it.

**The certificate identifies the publisher — you — and nobody else.** It is not
a licence, not a gate, and not a requirement for users. Anyone may install and
use Zaram: individuals, sole traders, people with no registered business at
all. Uploading a logo or a letterhead has nothing to do with this. Exactly one
identity gets verified, once, and it is the person shipping the software.

---

## The decision: OV. Not EV, and not "EV later either".

**An earlier version of this document said EV buys immediate SmartScreen
reputation. That is false, and it is worth recording as false**, because it is
the single most repeated piece of code-signing advice on the internet and it
would have cost real money.

Microsoft's own documentation, checked 12 August 2026:

> EV certificates no longer bypass SmartScreen. Years ago, signing files with
> an Extended Validation (EV) code signing certificate would result in positive
> SmartScreen reputation by default, but this behavior no longer exists. […]
> Paying a premium for EV solely to avoid SmartScreen warnings is no longer
> justified.

Their own table is blunter still. A **valid certificate, OV *or* EV**, gets:
"Warning — app flagged as unrecognized until reputation accumulates; verified
publisher name is displayed."

So the first download shows a warning either way. What signing buys is **your
name in that warning** instead of an unidentified publisher, and the ability to
accumulate reputation across releases at all — an unsigned build starts from
zero every version, forever.

| Path | First download |
|---|---|
| Microsoft Store | No warning — the only route that avoids it |
| OV or EV certificate | Warning until reputation accrues; your name shown |
| Unsigned or self-signed | Warning; no name; reputation can never accrue |

**Take OV, and only consider EV if enterprise procurement ever demands it** —
which is the one remaining reason it exists.

**Reputation attaches to the publisher identity.** Microsoft: "Use a consistent
signing identity — changing your signing certificate affects the publisher
trust signal." So a later move from an individual certificate to a business one
restarts reputation. Make that switch *during* the alpha, while the audience is
fifteen people you already know, or not at all.

### Signing matters more than the SmartScreen framing suggests

Two things raise the stakes beyond a click-through warning:

**Smart App Control on Windows 11 blocks unsigned executables outright** unless
the file has positive reputation — and unlike SmartScreen it applies to *all*
executables, not only downloaded ones. That is a hard block, not a prompt.

**Do not modify a file after signing.** Microsoft is explicit that it breaks the
signature. This bears directly on the plan to bundle a Python runtime: whatever
post-processing the installer does must happen *before* signing, never after.

---

## What you buy, and what you must not

Since **June 2023**, a publicly-trusted code signing private key must be held
on certified hardware. There are three shapes:

- **A USB hardware token** posted to you. Signing happens on the token. Add
  international shipping and customs to the validation time.
- **A cloud signing service.** No hardware to receive; credentials authorise
  signing against a remote HSM. Avoids the shipping delay, has its own
  eligibility rules.
- **Your own HSM.** Not worth considering at this stage.

**A `.pfx` file is not one of the options.** If a provider offers you a
downloadable key file for a publicly-trusted certificate, that is either a test
certificate nobody will trust or something that should not be possible.
`scripts/check-signing.mjs` refuses to sign a release from a key file for this
reason.

### Before contacting a provider

Have ready:

- The **exact legal name** you want in the Windows prompt. This is effectively
  permanent branding — users will see it on every install. Changing it means a
  new certificate and reputation starting over.
- Identity documents for that name.
- A verifiable phone number and physical address. Some CAs verify against a
  third-party directory listing, which for an individual in Nigeria may be the
  slowest step. **Ask about this first** — it is the most likely thing to stall.

### Microsoft Artifact Signing: ruled out on geography, not on merit

Artifact Signing (formerly Trusted Signing) is Microsoft's own recommended
service for non-Store distribution — roughly $10/month, no hardware token, HSM
backed, CI-native. On the technical merits it beats buying a certificate and a
USB token outright, and it would keep the production key off the development
machine, which is the right architecture.

**It is not available here.** Microsoft's prerequisites, checked 12 August 2026:

> Public Trust certificates are available to organizations in the United States,
> Canada, the European Union, the United Kingdom, Australia, New Zealand, Japan,
> South Korea, Singapore, Switzerland, Norway, and Israel. **Individual
> developers must be located in the United States or Canada.**

Nigeria appears on neither list, so neither route is open — not as an individual
today, and not as a registered Nigerian company later. Recorded here so it is
not rediscovered as a good idea every few months. **Re-check before the public
beta**; the list has grown before and this is the option to take the moment it
includes Nigeria.

### Unverified, and worth confirming yourself

Pricing, current provider offerings, and whether a given CA validates a
Nigerian sole trader are not things this document should assert — they change,
and being wrong about them costs weeks. Treat the shape above as settled and
the specifics as something to confirm with two or three providers before
committing.

---

## What is already done in the repo

Nothing here needs revisiting when the certificate arrives.

**`electron-builder.yml`** names the identity by environment variable and never
names a key, because there is no key file to name. `certificateSubjectName`
selects the certificate from the **Windows certificate store**, which is how a
hardware token presents itself once its driver is installed: the certificate is
visible, the private key is not, and the signing happens on the token.

**Timestamping is configured, and it is not optional.** Without an RFC 3161
timestamp, every signature stops validating the day the certificate expires —
*including copies already installed on other people's machines*. A one-year
certificate with no timestamp would quietly break the alpha a year after it
shipped. With one, the signature proves it was made while the certificate was
live, and stays valid.

**`scripts/check-signing.mjs`** runs inside `npm run build:desktop` and fails
the build rather than warning. A development build is unsigned and that is
correct; a release build that is unsigned should not exist, and the difference
between them must not be somebody's memory at 2am. It refuses three things: a
release with no identity configured, any build signing from a key file, and a
config with no timestamp server.

**`.gitignore`** carries certificate patterns. A committed private key is a
revoked certificate — paid for again, and re-validated from scratch.

---

## When the certificate arrives

1. Install the token's driver and plug it in, or configure the cloud service.
2. Confirm Windows can see the certificate:

```bash
certutil -user -store My
```

3. Copy the subject exactly as it appears there.
4. Build a signed release:

```bash
ZARAM_RELEASE=1 ZARAM_SIGN_SUBJECT="<subject from step 3>" npm run build:desktop
```

5. Verify the result — do not assume it worked:

```bash
signtool verify /pa /v dist-electron/Zaram-0.1.0-x64.exe
```

6. Then verify it the way a user meets it: copy the installer to a machine that
   has never seen the repo, download it through a browser, and run it. What
   matters is whether SmartScreen appears and what name it shows — not whether
   the build printed success.

## Moving to EV later

Set `ZARAM_SIGN_SUBJECT` to the new identity. Nothing else in the build
changes, which is the reason the subject is a variable rather than a literal.

Expect SmartScreen reputation to start over, per the note above.

---

## The build environment needs one privilege

electron-builder extracts its `winCodeSign` cache using symlinks, which on
Windows requires **Developer Mode enabled or an elevated prompt**. Without it
the build fails while extracting two irrelevant *darwin* `.dylib` links, and
the error names 7-Zip rather than the privilege, so it reads as a corrupt
download. Pre-extracting the cache does not help — the directory is randomly
named per attempt.

This is why an installer has never been produced on this machine.
