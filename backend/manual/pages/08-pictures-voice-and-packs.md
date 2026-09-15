# Pictures, voice, and the optional packs

## Reading a picture

Attach a screenshot or a photo to a message. The text in it is read on your computer, by Windows' own text recognition, the moment you attach it — nothing is downloaded and nothing is sent. A model that can look at pictures gets the image too; one that cannot answers from the text, and says so. A photo with no text in it needs a model that can see.

## Drawing a picture

Ask — *draw me a lighthouse at dusk*. Zaram needs something that can draw: either **Flux** on your own graphics card (about 13 GB of weights, needs a card with room) or a cloud provider you connected — NVIDIA NIM and Together have free tiers, fal.ai is paid. **Settings → Images** chooses which is tried first. The first picture sent to a provider is asked about once, on that request; after that it just draws. If your graphics card is full, the cloud draws instead and the chat model stays loaded.

## Speaking and listening

Choose **Avatar** under Settings → Appearance and replies are spoken. Press the microphone in the conversation to dictate: hold to talk, or latch it for hands-free. Both run on your computer; your voice never leaves it. If nothing was heard, Zaram says so rather than sending nothing.

Dictated figures are marked for checking — *four twenty five* has been heard as *$425* and as *₦425*, and an invoice does not forgive that.

## The packs

![Settings → Packs: each pack with what it turns on, its size, and one button.](assets/packs.png)

Some things are optional downloads, because not everyone wants them and they are large. Nothing is asked at install; each is offered where you reach for it, and all of them are listed under **Settings → Packs**:

- **Speaking** — the avatar speaks its replies. About 290 MB. Needs a restart after installing.
- **Listening** — push-to-talk and hands-free dictation. About 81 MB.
- **Reading scans** — scanned PDFs and photographed pages. About 321 MB.

One button each, with the size shown; the download is recorded in Activity like anything else.

## The avatar

The orb and the avatar are two ways of showing the same thing: what Zaram is doing — idle, working, listening, speaking. The avatar is not a character with moods; it embodies state. You can name Zaram, give it a manner and a voice under **Settings → Character**, and bring your own VRM avatar file. Asked what it is, it will always tell you: your name for it, that it is Zaram, and which model is answering.
