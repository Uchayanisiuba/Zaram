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

## Something was answered wrongly

Correct the fact in **Memory**. Every later answer changes. If the source document is wrong, fix the document; Zaram re-reads a watched folder on its own.

## Uninstalling

Uninstall from Windows as usual. The uninstaller asks what to do with your data — keep it, save a copy to the desktop and then delete it, or delete it. Keeping is the default; reinstalling picks it up again. An update never asks.

## Where things are

- Your memory, documents, log and settings: `%APPDATA%\Zaram`
- The program: `%LOCALAPPDATA%\Programs\Zaram`
- Documents Zaram made: the output folder shown in Work
