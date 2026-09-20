# Tools, projects, and working on code

## Tools

A tool is a program Zaram can use inside a conversation — a 3D application, a database, your code project. Tools speak a common protocol called **MCP**, so any server written for it can be attached under **Settings → Tools** by pasting its configuration. Zaram lists what each tool can do, and asks before a tool changes anything or sends anything anywhere. Tools never get their own menu; you ask for what you want in the conversation and Zaram reaches for the tool.

The first time a tool that changes things is used in a project, Zaram asks once. Reads are free.

When a tool is held for your say-so, the row that holds it offers **Allow — for this conversation · always**. *Once* is the plan's own Go. A few things are never allowed, whatever you grant: Zaram's own settings and credentials, and anything that looks like it deletes.

A model that can call tools decides for itself when to use one — you do not have to name the tool. Zaram still asks before anything changes or leaves.

## Projects

A **project** groups work: its files, the facts that belong to it, and the tasks in flight. Create one under **Project**, give it a type, and open it; questions are then answered with that project's facts first, and documents you make are filed under it. Deleting a project asks what to do with its facts and files rather than just removing them.

## Working on code

Open a project of type *coding* with a folder that holds a repository. Zaram then reads the code, searches it, edits files, and runs the project's own commands — its tests, its type checker, its build — never a free shell.

What that looks like:

- **Every edit is a git commit** with the command that undoes it. If you have uncommitted changes to a file, Zaram will not edit that file — your work is not swept into its commit.
- **A failed run names where it failed** and shows the code there, so the next step is a fix rather than a search.
- **Before calling a change done, Zaram runs the project's check** — type checker, linter or build, whichever the project has — and if it fails, fixes it or tells you what it could not.
- **Tests failing twice** brings an offer: a stronger cloud model for this step, with what would leave named on it. One button, never automatic.
- **Running the app**: Zaram can start your app, read the address it prints, and take a screenshot of it, read by a model on your machine.

Long tasks carry on across the model's memory limit on their own. A task that stops short is kept, with a **Continue** button, and survives a restart.

## Work that runs on its own

Under **Settings → Runs on its own**, give Zaram a question and a time: every day at nine, every Monday, or *when an obligation is coming up* — one run per commitment due within the next week, drafting the message that should go out about it. A run is an ordinary conversation, made without you: it recalls, plans, and uses tools exactly as a typed question does, and the first thing that needs your say-so **stops it** and files it under **Activity**, at the top, with the unfinished tasks — each with **Continue**. Nothing that runs on its own can approve itself, and nothing is ever sent. Three held runs in a row pause the trigger until you have looked.

What it made is under **Activity → Ran on its own**, each with **open** to the transcript.

## Giving the graphics card back

A local model stays loaded so the next answer is quick. **Settings → Models → Release the card** unloads it now, for a game or a render, and says what it could not unload. Closing Zaram does the same on its way out.

## The summon key

**Ctrl+Shift+Space**, from any application, opens a small Zaram panel over what you are doing, with the text you had selected already in it. Zaram reads the selection when you press the key and at no other time; it never watches what you type. Anything you send from the panel is governed like anything else — if it would go to a cloud model, the panel says so first.
