# Building apps and pages

Ask Zaram for a calculator, a landing page, a dashboard, a game or a small tool, and it writes the page and lets you run it right there. You do not need a project, a folder or a terminal for this.

## Asking for one

Describe what you want in plain words: *"a snake game, one file, arrow keys, a score and a game over screen"*. Zaram writes the page. Under the reply you get two buttons: **Preview**, which runs it, and **Save**, which keeps it.

Say what you want it to do rather than how to build it. If you want it without any libraries, say so. If you want it in several files, say that.

## The preview

![A page Zaram wrote, running in the preview beside the conversation. The line under the reply says the page ran without errors.](assets/app-preview.png)

**Preview** opens the page over the orb, beside the conversation, and runs it. The preview has no network access, so a page cannot send anything anywhere or load anything from the internet. Two things follow from that:

- A page that asks for a font, a stylesheet or a library from a website will look unfinished or stop. Zaram tells you which host it asked for.
- **three.js is built in**, along with its orbit, first-person and pointer-lock controls and its noise helpers. A 3D page that loads three.js the usual way works with the connection down, and Zaram says when it used its own copy.

While a page runs you can **Pause** it, **Restart** it from the top, and switch from **Page** to **Code** to read the exact code that is running. The keys, the mouse and pointer lock work as they would in a browser.

## Checked before you see it

When a reply contains a whole page, Zaram runs it first in a hidden browser that has no route to any website, and the line under the reply says what happened:

- **Ran without errors.** The page started, stayed up for a few seconds and reported no error. If it held the window still for several seconds while it started, the line says how long.
- **It did not run: …** The page froze or threw an error. Zaram sends the problem back to the model as a message in the conversation and asks for a fix. It does this **twice at most**. After that the line says the page still does not run and leaves it with you.
- **Not checked: …** Nothing could run it, for example because Chrome or Edge is not installed. That is not a pass, and the line does not say it is.

The check proves a page starts, stays up and throws no error. It does not play the game. Whether the floor holds or the score counts is for you to find out in the preview, and **Fix this** is there for what you find.

**Page check on/off** sits at the bottom of the conversation, beside **Thinking**. Turn it off and pages are shown as written. A short snippet inside an answer, such as a few lines of HTML, is never run or sent back.

## Changing a page

- **Select.** In the preview, press **Select**, click a part of the page, and say what to change. Zaram sends back the whole updated page.
- **Fix this.** When a page stops with an error, one press hands the error back to the model.
- **Revise**, under the reply, works on pages too.

Every change comes back as the **whole page**, never only the lines that changed, because a fragment cannot be run.

## One file or several

A small app is one file with its markup, style and script together. A bigger one can be several files. Zaram runs them together in the preview when the reply names each file, for example `index.html`, `style.css` and `game.js`, and links them by their names. A file may also import another one.

**Save** keeps what you have:

- A one-file page downloads as a single `.html` file you can open in any browser.
- An app of several files is written as a **new folder** in Zaram's output folder, under `apps`. The line next to the button shows exactly where. Zaram never overwrites a folder that is already there. If the name is taken, the new one gets a number.

Apps of several files stick to plain HTML, CSS and JavaScript. Anything the page reads while it runs, such as levels or pictures, has to be inside those files, because the preview does not let a page fetch files.

## When you need a project instead

Some apps need more than a browser: installing packages with `npm`, a development server, a back end, a database. That is working on code, and it needs a coding project with a folder, because running commands on your machine is something Zaram asks you to switch on. See *Tools, projects, and working on code*. A folder saved from the preview can be opened as a project later.

## Thinking, for code

**Thinking** has three settings: off, for code, and on. *For code* thinks only when you ask for code or a page, or when you are changing one, and answers everything else straight away. It is off until you choose it, because thinking can take a long time on a large model, and Zaram has not measured whether it improves pages. If a reply is still thinking after a long wait, Zaram offers **Answer without thinking** for that message.

## If it goes wrong

- **The page is blank or stuck.** Open **Code** and look. Press **Fix this** if the preview shows an error.
- **Zaram says a loop never ends.** The preview refuses to start a page with a `for` loop that never changes its counter, because it would freeze the window. **Fix this** asks the model to correct it. **Run anyway** is there if you want to see it for yourself.
- **The page check says it held still for several seconds.** The check runs without a graphics card, so the time is usually shorter on your machine. A page that stays blank for several seconds still reads as broken, so ask for the first screen to appear before the heavy work.
