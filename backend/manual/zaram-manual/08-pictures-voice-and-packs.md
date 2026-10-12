# Pictures, voice, and the optional packs

## Reading a picture

Attach a screenshot or a photo to a message. The text in it is read on your computer, by Windows' own text recognition, the moment you attach it — nothing is downloaded and nothing is sent. A model that can look at pictures gets the image too; one that cannot answers from the text, and says so. A photo with no text in it needs a model that can see.

## Drawing a picture

Ask — *draw me a lighthouse at dusk*. Zaram needs something that can draw: either **Flux** on your own graphics card (about 13 GB of weights, needs a card with room) or a cloud provider you connected — NVIDIA NIM and Together have free tiers, fal.ai is paid. **Settings → Images** chooses which is tried first. The first picture sent to a provider is asked about once, on that request; after that it just draws. If your graphics card is full, the cloud draws instead and the chat model stays loaded.

## Speaking and listening

Choose **Avatar** under Settings → Appearance and replies are spoken. Press the microphone in the conversation to dictate: hold to talk, or latch it for hands-free. Both run on your computer; your voice never leaves it. If nothing was heard, Zaram says so rather than sending nothing.

Dictated figures are marked for checking — *four twenty five* has been heard as *$425* and as *₦425*, and an invoice does not forgive that.

## Choosing a voice

![Settings → Character → Voice, with the voice list open: Test and Use beside the voices on this machine, Download beside the rest.](assets/voices.png)

Zaram speaks with **Kokoro**, which runs on your computer's processor and so does not compete with a local model for the graphics card. It has 54 voices. Open **Settings → Character → Voice → Browse 54 voices** to see them all, grouped by language:

- **Test** plays a short sample in that voice. Nothing changes.
- **Use** makes it the voice that speaks your replies. The one speaking now is marked *speaking*.
- **Download** fetches a voice that is not on your computer yet — about half a megabyte each, from huggingface.co. Pressing it is your permission for that one file, and it is logged in Activity. A downloaded voice is not chosen until you press Use, so you can collect a few and compare.
- A greyed voice needs a language pack — Japanese or Chinese, for example — and says which.

The line above the list names the speech engines. Kokoro is the only one built; the others are listed so you can see what is planned, and none of them can speak yet.

**Settings → Voice Engine → Local Voice Cleanup** removes the voices you downloaded and are not using, keeping the one that speaks now. It shows how many it would remove first.

## The packs

![Settings → Packs: each pack with what it turns on, its size, and one button.](assets/packs.png)

Some things are optional downloads, because not everyone wants them and they are large. Nothing is asked at install; each is offered where you reach for it, and all of them are listed under **Settings → Packs**:

- **Speaking** — the avatar speaks its replies. About 290 MB. Needs a restart after installing.
- **Listening** — push-to-talk and hands-free dictation. About 81 MB.
- **Reading scans** — scanned PDFs and photographed pages. About 321 MB.

One button each, with the size shown; the download is recorded in Activity like anything else.

## The avatar

The orb and the avatar are two ways of showing the same thing: what Zaram is doing — idle, working, listening, speaking. The avatar is not a character with moods; it embodies state. You can name Zaram, give it a manner and a voice under **Settings → Character**, and bring your own VRM avatar file. Asked what it is, it will always tell you: your name for it, that it is Zaram, and which model is answering.
