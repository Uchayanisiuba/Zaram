# Tools, projects, and working on code

## Tools

A tool is a program Zaram can use inside a conversation — a 3D application, a database, your code project. Tools speak a common protocol called **MCP**, so any server written for it can be attached under **Settings → Tools** by pasting its configuration. Zaram lists what each tool can do, and asks before a tool changes anything or sends anything anywhere. Tools never get their own menu; you ask for what you want in the conversation and Zaram reaches for the tool.

The first time a tool that changes things is used in a project, Zaram asks once. Reads are free.

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

## The summon key

**Ctrl+Shift+Space**, from any application, opens a small Zaram panel over what you are doing, with the text you had selected already in it. Zaram reads the selection when you press the key and at no other time; it never watches what you type. Anything you send from the panel is governed like anything else — if it would go to a cloud model, the panel says so first.
