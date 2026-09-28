"""`check_eligibility` and `read_criteria`: the gate, as tools the model can choose.

Same shape as the web and draw packs — a built-in MCP server in process, so it
inherits the policy gate, the injection scan on results, the tool budget rules
and the egress log without a second mechanism.

**Both tools are deterministic and neither touches the network.** They read
text the caller already has and answer from stored facts. That is deliberate:
this is the half of the pack that must reproduce, because a refusal the user
disputes has to come out the same way the second time for the correction loop
to have anything to bite on.

**What is not here, and why.** There is no `apply` tool and there will not be
one. `docs/PACK-OPPORTUNITIES.md` has the reasoning: Grants.gov's own API
documentation says applications cannot be submitted through it, the EU portal
has no submission endpoint, and rules 6, 9 and the mutative tier all land on
the same line independently. The pack stops at a review queue that a person
presses send on.

There is also no `find_opportunities` yet. Fetching goes through the egress
gate, the poller is step 2 of the shipping order, and a tool that promises to
search and cannot is worse than no tool — `CLAUDE.md`'s own rule about a
search nobody wired: *"a search nobody wired is not a capability, and listing
it would promise something the machine cannot do."*
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

from runtimes.mcp.client import ToolDescriptor

from .contracts import Opportunity, OpportunityKind, Profile, Verdict
from .eligibility import assess
from .requirements import read_requirements

logger = logging.getLogger(__name__)

__all__ = ["OpportunityTools", "SERVER_ID", "CHECK_ELIGIBILITY", "READ_CRITERIA"]

SERVER_ID = "opportunities"
CHECK_ELIGIBILITY = "check_eligibility"
READ_CRITERIA = "read_criteria"

#: A call's text is untrusted third-party text and sits in the model's context
#: beside everything else, so what comes back is bounded. Generous enough to
#: carry a real eligibility section, short enough that one funder's terms
#: cannot become the whole window.
MAX_TEXT = 20_000


class OpportunityTools:
    """Zaram's built-in opportunities server: the eligibility gate."""

    def __init__(self, profile: Optional[Callable[[], Profile]] = None) -> None:
        # Resolved at call time rather than at boot, so the tool answers from
        # the profile as it stands now. A snapshot taken at startup would be
        # wrong the moment the user corrected a fact — which is rule 4's whole
        # promise, and the reason the web pack resolves its search switch the
        # same way.
        self._profile = profile

    # -- the built-in server surface ------------------------------------------ #

    def connect(self) -> None:
        """Nothing to start. Present because the runtime calls it."""

    def close(self) -> None:
        """Nothing to stop."""

    def granted_tools(self) -> set:
        """Always offered.

        Neither tool sends anything anywhere or changes anything, so there is
        no consent question to hold them behind. `check_eligibility` without a
        profile still answers — it reports that nothing is known, which is the
        answer that prompts the user to say.
        """
        return {CHECK_ELIGIBILITY, READ_CRITERIA}

    def list_tools(self) -> List[ToolDescriptor]:
        return [self._check_descriptor(), self._read_descriptor()]

    def _read_descriptor(self) -> ToolDescriptor:
        return ToolDescriptor(
            server_id=SERVER_ID,
            name=READ_CRITERIA,
            description=(
                "Read the eligibility criteria out of a job posting or a funding "
                "call. Give it the text of the call. Returns each requirement it "
                "found with the exact sentence that states it. It is deliberately "
                "conservative and reports only what the text says plainly, so an "
                "empty result means nothing was stated clearly — never that there "
                "are no requirements. Say that distinction plainly to the person; "
                "do not report 'no requirements' when nothing was read."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The posting or call text to read.",
                    }
                },
                "required": ["text"],
            },
        )

    def _check_descriptor(self) -> ToolDescriptor:
        return ToolDescriptor(
            server_id=SERVER_ID,
            name=CHECK_ELIGIBILITY,
            description=(
                "Check whether the person can actually apply for a job or grant. "
                "Give it the text of the call. Answers eligible, ineligible or "
                "unknown, with the sentence behind each part of the answer. "
                "'unknown' means a fact about the person is missing and should be "
                "asked for — it never means no. Use this before drafting anything: "
                "a funding application the person was never eligible for costs them "
                "a fortnight."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The posting or call text to check.",
                    },
                    "title": {
                        "type": "string",
                        "description": "What the role or call is called, if known.",
                    },
                },
                "required": ["text"],
            },
        )

    def call_tool(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        arguments = arguments or {}
        text = str(arguments.get("text") or "")
        if name == READ_CRITERIA:
            return self.read_criteria(text)
        if name == CHECK_ELIGIBILITY:
            return self.check_eligibility(text, title=str(arguments.get("title") or ""))
        return {"error": f"the opportunities server has no tool called {name!r}"}

    # -- the tools ------------------------------------------------------------ #

    def read_criteria(self, text: str) -> Dict[str, Any]:
        if not text.strip():
            return {"error": "there was no text to read — paste the posting or the call"}

        requirements = read_requirements(text[:MAX_TEXT])
        return {
            "found": len(requirements),
            "requirements": [r.to_dict() for r in requirements],
            # Said in as many words rather than left to be inferred from a zero.
            # "Nothing was read" and "nothing is required" are different claims
            # and a model handed only a count will state the second one.
            "note": (
                "Nothing was stated plainly enough to read. That is not the same as "
                "there being no requirements — say so rather than reporting the call "
                "as unrestricted."
                if not requirements
                else "Each requirement carries the sentence it was read from."
            ),
        }

    def check_eligibility(self, text: str, *, title: str = "") -> Dict[str, Any]:
        if not text.strip():
            return {"error": "there was no text to check — paste the posting or the call"}

        profile = self._profile() if self._profile else Profile()
        opportunity = Opportunity(
            id="ad-hoc",
            kind=OpportunityKind.GRANT,
            title=title,
            organisation="",
            url="",
            feed_id="ad-hoc",
            body=text[:MAX_TEXT],
            requirements=read_requirements(text[:MAX_TEXT]),
        )
        report = assess(opportunity, profile)

        answer = report.to_dict()
        answer["title"] = title
        answer["summary"] = _sentence(report.verdict, report)
        return answer


def _sentence(verdict: Verdict, report) -> str:
    """The verdict as a person would say it.

    A sentence rather than a number, because the whole point of this gate is
    that it can be argued with — and a score cannot be. The blocking finding's
    own reason is used verbatim, so what the user reads is what the clause
    said.
    """
    if verdict is Verdict.INELIGIBLE:
        blocking = report.blocking
        return blocking[0].reason if blocking else "Not eligible."
    if verdict is Verdict.UNKNOWN and report.checked == 0:
        return (
            "No requirements were stated plainly enough to read. That is not the "
            "same as there being none."
        )
    if verdict is Verdict.UNKNOWN:
        return "Eligible so far, but some of it depends on facts Zaram does not have yet."
    return "Eligible on everything the call states."
