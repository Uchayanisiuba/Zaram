# Building apps and pages

Ask Zaram for a calculator, a landing page, a dashboard, a game or a small tool, and it writes the page and lets you run it right there. You do not need a project, a folder or a terminal for this.

## Asking for one

Describe what you want in plain words, including how it should behave. For example, this is the prompt used to test the Minecraft-style game on this page:

> *Build a Minecraft-style 3D game in HTML that I can play in my browser. Walk around a blocky world, mine blocks and place them, and make sure the floor collision works so I start standing on the ground. Keep it light enough to run on my PC alongside Zaram.*

Zaram writes the page. Under the reply you get two buttons: **Preview**, which runs it, and **Save**, which keeps it.

Say what you want it to do rather than how to build it. The more you say about how it should look and feel, the closer the first try is — and a picture helps: attach a screenshot of something like what you want, and Zaram reads it. If you want it without any libraries, say so. If you want it in several files, say that.

**Your own pictures can go in the page.** Attach photos to the message and ask — *make me a portfolio site using these photos* — and the page shows them. Zaram gives each picture a short name (your own file name if it is plain, otherwise `photo-1.jpg`), tells the model only the names, and puts the pictures in on your computer when the page runs or is saved; the pictures themselves are never sent to the model as text. A later message such as *make the first photo bigger* still knows which picture is which. Saved, a single page carries its pictures inside it, and an app of several files carries them inside its files. Photos in a format a browser cannot show (HEIC, TIFF) cannot go in a page, and the model says so. Pictures belong to the conversation they were attached in, and Zaram keeps a copy with that conversation on your computer, so a page still shows them after a restart or when you open the conversation again from History; they are never searched, remembered or sent anywhere. The copies stay as long as the conversation does and are deleted when you delete it, and all the conversations together keep at most 1 GB: past that, the pictures of the conversation you have used least recently go first. To remove them sooner without losing the conversation, use the picture button beside it in History. Wherever a picture is gone, the page shows a grey placeholder where it was, and the line under the reply says which picture to attach again.

**Real photos for a site.** Ask for a site that would have photographs — *build a tourism website for Lagos with a gallery of beaches and markets* — and Zaram finds them for you. The model describes each photo it wants (*Lagos beach at sunset*) instead of making up a picture, and when the reply is finished Zaram searches [Openverse](https://openverse.org), a free library of openly licensed photos, and puts the best match for each into the page. It works like this:

- **You are asked once for each source.** The first time, Zaram shows you exactly what it would search for and asks before anything is sent. Say yes and it remembers, for Openverse only; change your mind under **Activity → Destinations**. Every search and download is in the egress log.
- **A second source, asked separately.** If Openverse has nothing usable for a photo, or has hit its free limit, Zaram can try [Wikimedia Commons](https://commons.wikimedia.org), which is also free and openly licensed. That is a different destination, so you are asked about it on its own, once, with the descriptions it would search for. Its pictures are served from a second address, `upload.wikimedia.org`, and your yes names and covers both. Say no and nothing is sent there; the photos Openverse could not find stay grey cards.
- **Only the descriptions leave your machine** — never your files or anything Zaram remembers about you. A description that would carry something from your memory is not sent.
- **Every photo is credited.** The page gets a line at its foot naming each photo, its photographer, its licence and the source it came from, with links. Only photos you are allowed to use and change are chosen.
- **A photo that cannot be found is a labelled grey card**, saying what should be there and why — never a guessed picture. If you said no, the connection dropped, a source's free limit was reached, or Zaram stopped after a minute so the page was not held up, **Find photos again** appears under the reply.
- **Zaram stays under the free limits instead of hitting them.** Openverse allows only about twenty requests a minute, so Zaram spaces its requests and waits a few seconds when it has to, rather than failing. It never waits more than about twenty seconds for one request, or a minute for the whole page.
- **A photo it already found is reused.** Asking for the same description again, on a later page or after reopening one, takes the photo from your computer with no new request. Zaram keeps the most recent 80 photos and forgets which description found which when it drops one; the record of what was looked for is only the egress log.
- When your request names a place, Zaram looks for photos of that place first, and falls back to the subject alone (*beach*) when there are none.
- Up to eight photos a page. A saved page carries the photos inside it.

## Tested starting points

Some games are hard to get right from nothing: a 3D game has to get movement, gravity and collision exactly right, and a small mistake means you fall through the floor, cannot walk, or steer the wrong way. So for three kinds of game Zaram starts from a page it has already played, and the model changes only what you asked for. There are three:

- **A Minecraft-style, voxel or blocky world.** Walking, jumping, swimming, mining, building, a hotbar of blocks, and a start and pause screen.
- **A racing game.** A car on a closed track with a chase camera. W or the up arrow accelerates, S or down brakes and then reverses, A and D steer, and the grass slows you down instead of stopping you. A lap only counts if you went through every checkpoint, in order, so reversing over the line gains nothing. It shows the lap, your lap time and your best. Try: *"a racing game with a longer, twistier track, five laps, a blue car, and a faster top speed."*
- **A 3D platformer or obstacle course.** A character you run and jump with, behind an orbiting camera: WASD moves relative to where the camera looks, Space jumps, and you can still jump for a moment after running off an edge. There are platforms that slide and carry you, coins to collect, checkpoints, and a flag at the end that shows a win screen. Fall off and you go back to the last checkpoint. Try: *"a 3D obstacle course with lava-red platforms, twice as many coins, and a lift that goes higher."*

How it works for all three:

- A plain request comes back in about a minute and a half on a local model, because nothing needs changing. The line under the reply says *Built on Zaram's tested voxel-world starting point* (or *racing*, or *platformer*).
- Ask for more and the model changes the starting point to suit: *"a bigger world, 96 by 96 blocks, an evening orange sky, a faster sprint, and add a brick block to the hotbar."* Sizes, speeds and colours sit together at the top of each page, and the racing track and the platformer course are each a short list the model edits.
- They are light on purpose: no lights or shadows, a few large pieces of scenery rather than thousands of small ones, and the screen drawn at its normal size. They run beside a local model that fills the graphics card.
- If a game cannot lock the mouse, it still plays: the racing game uses only the keyboard, and in the others you drag to look around.
- It only happens for a 3D game. Ask for a *2D* or *top-down* racer or platformer and the model writes it without a starting point.
- Want it written from nothing instead? Say *from scratch* and no starting point is used.

Other kinds of 3D game are written from the page guidance alone, and changed and checked the same way.

## The preview

![The Minecraft-style game from this page, changed to an evening sky with a brick block, running in the preview beside the conversation. The reply holds only the changes, and the line under it says the game was built on the tested starting point and ran without errors. The 20 fps in the corner is the screenshot's software renderer; on a graphics card it runs at 60.](assets/app-preview.png)

**Preview** opens the page over the orb, beside the conversation, and runs it. The preview has no network access, so a page cannot send anything anywhere or load anything from the internet. Two things follow from that:

- A page that asks for a font, a stylesheet or a library from a website will look unfinished or stop. Zaram tells you which host it asked for.
- **three.js is built in**, along with its orbit, first-person and pointer-lock controls and its noise helpers. A 3D page that loads three.js the usual way works with the connection down, and Zaram says when it used its own copy.

While a page runs you can **Pause** it, **Restart** it from the top, and switch from **Page** to **Code** to read the exact code that is running. The keys, the mouse and pointer lock work as they would in a browser.

## Checked before you see it

When a reply contains a whole page, Zaram runs it first in a hidden browser that has no route to any website, and the line under the reply says what happened:

- **Ran without errors.** The page started, stayed up for a few seconds and reported no error. If it held the window still for several seconds while it started, the line says how long.
- **Zaram put back a missing step (`++`) in a loop.** A local model sometimes drops the `++` from a `for` loop, which would freeze the page. There is only one thing such a loop can mean, so Zaram puts it back and says so, instead of spending a round asking the model to fix it.
- **It did not run: …** The page froze or threw an error. Zaram sends the problem back to the model as a message in the conversation and asks for a fix. It does this **twice at most**. After that the line says the page still does not run and leaves it with you.
- **Not checked: …** Nothing could run it, for example because Chrome or Edge is not installed. That is not a pass, and the line does not say it is.

The check proves a page starts, stays up and throws no error. It does not play the game. Whether the floor holds or the score counts is for you to find out in the preview, and **Fix this** is there for what you find.

**Page check on/off** sits at the bottom of the conversation, beside **Thinking**. Turn it off and pages are shown as written. A short snippet inside an answer, such as a few lines of HTML, is never run or sent back.

## Changing a page

- **Select.** In the preview, press **Select**, click a part of the page, and say what to change.
- **Fix this.** When a page stops with an error, one press hands the error back to the model.
- **Revise**, under the reply, works on pages too.

A change comes back as **only the lines that change**, and Zaram applies them to the page you already have, so you still get the whole page to preview and save. On a local model that is a minute or two rather than twenty: the model no longer writes the whole game out again to change two lines, and it cannot break the parts it did not touch. If a change does not match the page, Zaram says which one and asks again.

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
- **Zaram says a loop never ends.** The preview refuses to start a page with a `for` loop that never changes its counter, because it would freeze the window. Zaram repairs the usual case itself; when it cannot tell what the loop meant, **Fix this** asks the model to correct it. **Run anyway** is there if you want to see it for yourself.
- **It runs but does not play right.** The check proves the page starts; it does not play the game. Say what is wrong in plain words — *"W walks sideways"*, *"I fall through the ground"* — and the model fixes those lines.
- **The page check says it held still for several seconds.** The check runs without a graphics card, so the time is usually shorter on your machine. A page that stays blank for several seconds still reads as broken, so ask for the first screen to appear before the heavy work.
