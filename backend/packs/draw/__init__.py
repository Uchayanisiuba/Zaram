"""The draw pack: a picture as a step of the work.

Zaram could draw before this pack and could not draw *during* anything.
Generation was an intent — `IntentPlanner` matching "draw me a picture" and
routing the whole request to an image-capable model — so one request bought one
picture and nothing else, and *"write the proposal and put a cover image on
it"* was two conversations with a copy-paste between them. The model was never
handed a verb for it, so it could not decide a step wanted one.

`draw_image` is that verb, on Zaram's own built-in server, offered through the
same loop, gate and log as every other tool.

**Nothing about drawing is re-implemented here.** The tool calls
`ImagesRuntime`, which already owns the modality gate (can this model *emit* an
image, which is a precondition and never a score), the card check, the refusal
with its remedy and its size, the provider's data policy, and the
`ArtifactService` that documents also write through. One capability, one write
path, one no-overwrite guarantee.

**Generative tier**: it creates a new file and can destroy nothing, so it needs
no undo, no sandbox and no confirmation, and is granted rather than gated. The
consent that applies is about the *destination* — an image is its own data
class under rule 7j, and a provider permitted for text is not thereby permitted
for a photograph — and that decision lives in the runtime and the egress gate,
where it governs a directly-requested picture identically.

**The refusal is the part to get right.** Most machines cannot draw at all.
When that is the state the tool says so, with the remedy, and tells the model
to carry on and admit the picture was not made — because a text model narrating
an image it never drew is rule 9's failure in a new medium, and it is the
failure this pack must not invite.
"""

from .tools import DRAW_IMAGE, SERVER_ID, DrawTools

__all__ = ["DrawTools", "DRAW_IMAGE", "SERVER_ID"]
