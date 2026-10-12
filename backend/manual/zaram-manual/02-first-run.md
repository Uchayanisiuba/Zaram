# The first time you open Zaram

Zaram works the moment it opens. Nothing has to be downloaded first, and no account is needed.

## What happens on the first run

1. Zaram looks at your computer: how much memory your graphics card has, and whether a local AI model is already installed.
2. It asks one question — what you will mostly use it for — so it knows which kind of answers to prefer.
3. It shows what it found and offers to **start with what you have**.
4. If you want more reach, it offers a cloud key. This is optional; everything works without it.
5. It asks for one folder to read, so the first answer you get can cite something of yours.

## A local model

Zaram runs models through **Ollama**, a free program that keeps AI models on your computer. If Ollama is installed, Zaram finds its models and offers to download a good one for your machine, with the size shown before anything moves. If Ollama is not installed, Zaram says so and tells you where to get it, and you can use a cloud key in the meantime.

A local model is free to use, works with the internet off, and nothing you say to it leaves your computer.

## Model servers start with Zaram

![Settings → Models → Model servers on this machine: Ollama and TabbyAPI running, each with Starts with Zaram.](assets/model-servers.png)

If you have a model server installed — **Ollama**, or **TabbyAPI** — and it is not running, Zaram starts it when it opens, so your models are there without you remembering to start anything in another window. **Settings → Models → Model servers on this machine** lists each one, what it holds, and a **Starts with Zaram** switch for each.

Zaram never installs or updates a server, and it never stops one it started: the same server may be serving another program. To give the graphics card back for a game or a render, use **Release the card** on the same screen.

## A cloud key

A key is a long code you get from a provider — NVIDIA, OpenRouter, Groq, Google and others give one away without a card. Paste it under **Settings → Cloud providers** and press Connect. That is the only setup: Zaram permits that provider, picks a model for each kind of job, and tells you what the provider does with your data. Free cloud tiers are usually paid for with your data — Zaram names that beside each one.

## What you do not have to decide now

Voices, the microphone, reading scanned documents, drawing pictures and computer use are all optional. Zaram never asks about them at install. Each is offered the moment you reach for it — turn on the avatar and it offers the Speaking pack, press the microphone and it offers Listening — with the size shown, one button, once.
