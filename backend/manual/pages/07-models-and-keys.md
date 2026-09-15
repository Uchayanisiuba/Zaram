# Models, keys, and what leaves your computer

## Local and cloud

A **local** model runs on your own computer through Ollama or a similar program. It is free per question, works offline, and nothing you say to it leaves the machine. A **cloud** model runs on a provider's servers and needs a key. Zaram can use both, and decides per question which answers — or you decide.

## Three levels of control

![Settings → Models: the routing choice, the connected providers, and Advanced.](assets/settings.png)

1. **Zaram decides.** The default. It picks one local and, if you have a key, one cloud model, and routes each question to the better fit.
2. **Prefer local · Auto · Prefer cloud.** One control under **Settings → Models**. *Prefer local* keeps everything on your machine unless nothing here can do it.
3. **Per task**, under **Advanced**: which model answers coding questions, questions about pictures, and writes documents. Most people never need this.

Every reply names the model that answered and whether it ran here.

## Adding a cloud key

To add a cloud key: **Settings → Cloud providers → pick a provider → paste the key → Connect.** That is the whole setup. Zaram then:

- permits that provider's servers for your questions — connecting is the consent, so you are not asked twice;
- offers to pair a model to each job (chat, code, pictures, documents) with one click — *See picks*, then *Assign these*;
- tells you the deal: whether that provider keeps and trains on what you send. Free tiers usually do; Zaram never routes to one of those on its own.

Providers that give a key without a card: NVIDIA NIM, OpenRouter, Groq, Google Gemini, Cerebras, GitHub Models.

## What leaves, and the log

Nothing leaves your computer unless you allowed that destination. Connecting a provider allows your questions to it. **A picture is a separate decision**: the first time a picture would go to a provider, Zaram asks once, on that request, and remembers your answer. Facts recalled from your memory going to a new destination are asked about the same way.

**Activity → What left** is the log: every request that went out, where, when, and what was in it. It cannot be edited, and it records refusals too.

## Cutting everything off

**Activity → Destinations** lists every server Zaram has ever contacted, with a switch for each: allow, ask, block. *Block everything* stops all outbound traffic at once. A local model keeps working.

## Search on the web

Off unless you turn it on, under Settings. When on, Zaram may look things up for questions that need current information, and shows what it found as a source. Pages it reads are logged like anything else.

## When a cloud model is switched off

Providers change and models get withdrawn — in June 2026 the best model available was switched off worldwide for eighteen days. Zaram is built so that your memory does not depend on any of them: remove every key and recall, correction and documents keep working on a local model.
