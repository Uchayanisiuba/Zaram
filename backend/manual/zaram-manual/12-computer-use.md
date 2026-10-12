# Computer use — letting Zaram work your desktop

Zaram can use the programs on your computer for you: open an app, read what is in a window, click, type, press keys, scroll and take a screenshot. You ask in the conversation, and it asks you before it changes anything.

It is off until you install it, and you can switch it off at any time without losing anything.

## Turning it on

![Settings → Computer Use: cua-driver installed and healthy, with the On and Off switch.](assets/computer-use.png)

1. Open **Settings → Computer Use** and press **Install cua-driver**.
2. Zaram downloads the driver from github.com — about 30 MB, which can take a few minutes on a slow connection. Pressing Install is your permission for that one download; it is written in **Activity** like anything else that leaves, and the file is checked against a fingerprint built into Zaram before anything is unpacked.
3. Zaram connects it as a tool. When the row says **cua-driver · HEALTHY** and *Ready*, it can read windows and act on them.

The driver comes from the company that makes it, and it would normally send that company anonymous usage counts. Zaram switches that off before the driver first runs, and keeps it off.

## Asking it to do something

Start your message with what you want done on the screen:

- *launch notepad*
- *type hello world*
- *click on the Start button*
- *press enter*
- *scroll down*

Or say it anywhere in a sentence: *take a screenshot*, *list windows*, *list apps*, *control my computer*, *move the mouse*, *bring Chrome to the front*. An ordinary question that happens to use one of those words — *what type of invoice should I send?* — is answered as a question, not as a request to touch your desktop.

Zaram usually starts by looking — which apps are running, what is in the window — and then acts on what it found.

## What it sees

When Zaram reads a window, the driver also takes a picture of it. The picture appears under the reply as **what Zaram saw**, so you can check what it was looking at. If the model answering can see pictures, it is shown the newest one as well; if it cannot, it works from the text of the window, which lists every button and field by name. Zaram keeps the last 40 pictures and removes older ones, because a picture of your screen is not something to keep forever.

## What it asks first

- **Looking is free.** Listing windows and apps, reading what is in a window and taking a screenshot run without asking.
- **Acting asks.** A click, typing, a key press, scrolling or opening an app asks the first time. Choose **Allow — for this conversation · always** and it stops asking about that action.
- **Some things ask every time**, whatever you allowed: closing an app, writing to the clipboard, downloading a file, and sending your browser to a web address.
- **Some things are never done.** Zaram will not let the driver check for its own updates, install extra programs or change its own settings, because those would reach the internet behind Zaram's back.

## Switching it off

The **On · Off** switch on the cua-driver row turns computer use off at once: the driver stops, the model is offered none of its tools, and any request to act on the screen is answered with *computer use is switched off* and where to turn it on. What you allowed and the program itself are kept, so switching it back on is instant — nothing is downloaded again.

**Remove**, under **Settings → Tools**, disconnects it completely and forgets what you allowed. Pressing **Install** again afterwards reconnects it without a new download.

The **kill switch** in Settings → Privacy does not turn computer use off: it stops what leaves your computer, and computer use acts on your computer. Use the On · Off switch.

## What leaves your computer

The driver works locally. What it reads — window titles, the text in a window, a screenshot — goes to whichever model is answering. With a model on your computer, that stays on your computer. With a cloud model, what it reads from your screen goes to that provider, so think about what is open before you ask a cloud model to look. A picture of a window is sent only to a cloud model that can see, and the first time, Zaram asks whether that provider may have pictures, the same question it asks before sending a photo you attached.

## Good to know

- **A stronger model does better.** Doing several steps on a desktop needs a model that is good at using tools. If a local model stops halfway, try the same request on a stronger model for that one message.
- **It works in the background.** The driver is built to act on a window without taking over your own mouse and keyboard, so you can keep working while it does.
- **Zaram has been tested on Windows.** The driver also supports macOS and Linux.
