# What Zaram is

Zaram is an assistant that remembers you, runs on your own computer, and works with more than one AI model.

## The one idea

Most AI apps keep what you tell them on their servers, tied to their model. Zaram keeps it on your machine, in one place called the **memory**, and any model you use — one on your computer, or one in the cloud through a key you added — can read from it. Switch models and nothing is lost.

## What it does, in plain terms

- **Answers from what it knows about you** — your documents, what you have told it, what was decided — and shows you where each answer came from.
- **Reads your files.** Point it at a folder, drop in a PDF, paste text, or attach a screenshot. It reads them here, on your machine.
- **Writes documents.** Proposals, reports, letters, invoices, spreadsheets, slide decks. They arrive as files you can open and send.
- **Remembers commitments.** Payment terms, deadlines and deliverables found in your documents, and tells you before they fall due.
- **Draws pictures and reads them**, when a model that can is available.
- **Talks and listens**, if you turn that on.
- **Uses tools** you attach — a 3D program, a code project, anything that speaks the MCP tool protocol — and asks before it changes or sends anything.

## What leaves your computer, and what does not

![Your memory and a local model stay on your computer. Anything bound for a cloud provider passes one gate, which asks once per destination and kind of data and writes a log line before it goes.](assets/where-things-go.svg)

Nothing leaves unless you decided it should. A model on your own machine costs nothing per question, and nothing you say to it goes anywhere or is trained on. If you add a cloud key, Zaram asks once per destination and per kind of data, remembers the answer, and keeps a log of every byte that left. The log is in **Activity**.

## How to start

Click the orb in the middle of the screen and type. That is the whole beginning. Everything else — folders, keys, voices, tools — can wait until you want it.

## The six places

![The landing: the orb in the middle, six places around it, and the status line below.](assets/landing.png)

Around the orb are six nodes. Each is one place:

- **Work** — the documents and files Zaram made for you.
- **Project** — groups of work, with their own facts and files.
- **Memory** — what Zaram remembers about you, and the commitments it found. You can correct or delete anything here.
- **Knowledge** — the folders and files Zaram reads, and the domains they are grouped into.
- **Activity** — what left your machine, and what Zaram has been doing.
- **Settings** — models, keys, packs, appearance, and help.

Conversation is not a place; it is where you already are. Click the orb to open it and click it again to close it.
