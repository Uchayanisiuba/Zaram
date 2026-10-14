# When something goes wrong

## Reporting a problem

**Settings → Help → Report a problem → Copy report.** This copies a short report to your clipboard: the version, your computer's hardware, the models Zaram found, your routing choices, and the last few things that left your machine — without their contents. It holds no conversation text, no document names, no remembered facts and no keys; the report says so at its top, so you can read it before you send it.

Then press **Send feedback**, which opens a short form in your browser — no account needed — and paste the report there with what you expected and what happened instead. A reply to the tester email, or an issue at github.com/Uchayanisiuba/Zaram/issues, works too. Zaram never sends anything on its own; the form is a page in your browser.

## Zaram says its engine is not running

The part of Zaram that thinks starts a few seconds after the window opens. If the notice stays, quit Zaram and open it again. If it persists, the log at `%APPDATA%\Zaram\logs\desktop.log` says why; the report above includes what a maintainer needs.

## Windows warned before installing

The alpha is not code-signed, so Windows shows a warning the first time. That is expected for this build. The release page lists the file's SHA-256 if you want to check what you downloaded.

## A cloud model answers from only the last message

The model's window is full. Zaram says so once, under the reply: quote what it needs to see, or switch to a model with a larger window. On a local model, a larger window can be set in the model's own settings in Ollama.

## Nothing here can draw

Drawing needs Flux on your graphics card or a cloud key with pictures allowed. Settings → Images shows what is available and what each needs.

## Computer use does nothing

Check **Settings → Computer Use**. The cua-driver row should say *HEALTHY* and its switch should be **On**; if it is off, Zaram answers that computer use is switched off rather than pretending. Then start the message with what to do — *click…*, *type…*, *launch…* — or say *take a screenshot* or *list windows*. If a local model stops partway through a task, try a stronger model for that message.

## A voice or a download says it was blocked

If you blocked that site on purpose, or the kill switch is on, a download stays blocked — that is the switch working. Look under **Settings → Privacy**.

## Something was answered wrongly

Correct the fact in **Memory**. Every later answer changes. If the source document is wrong, fix the document; Zaram re-reads a watched folder on its own.

## Updating Zaram

Zaram asks once whether it may check for a newer version when it opens, and the default is yes. A check asks GitHub for the list of releases and sends nothing about you, your computer or your work — no version number, no identifier. It is written to **Activity** like anything else that leaves, and you can turn it off, or press **Check now**, in **Settings → Updates**.

When a newer version exists a small card says so, with the size on the button. **Download** fetches the installer through the same gate as everything else, checks it against the SHA-256 published beside it, and keeps it. Nothing is installed until you press **Restart and install**: Zaram closes, the installer replaces it quietly, and the new version opens. Your memory, documents and settings are kept — an update never asks about them.

Two things it cannot do. The portable build cannot replace itself, so it opens the release page instead. And the builds are not signed yet, so Windows may show its usual warning the first time you install; the checksum guards against a damaged download, not against a release published by someone else with access to the repository. A build that was not made from a release (a development run) cannot tell what is newer and says so.

The very first update has to be done by hand: a copy installed before this existed cannot update itself. Install the newer one over it once, and every one after that comes from inside Zaram.

## Uninstalling

Uninstall from Windows as usual. The uninstaller asks what to do with your data — keep it, save a copy to the desktop and then delete it, or delete it. Keeping is the default; reinstalling picks it up again. An update never asks.

## Where things are

- Your memory, documents, log and settings: `%APPDATA%\Zaram`
- The program: `%LOCALAPPDATA%\Programs\Zaram`
- Documents Zaram made: the output folder shown in Work
