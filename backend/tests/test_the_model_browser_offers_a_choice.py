"""Every model the manifest knows, graded against this machine.

Asked for 4 October 2026 with a screenshot of LM Studio's model browser —
a searchable list with sizes, capability marks and a download button —
and the first-run case from a second screenshot: *"when the user opens
Zaram for the first time and has no model ... users are able to click on
the download models button and select relevant models for their PC."*

`/readiness` already offers exactly one model, *the first of the tier*.
That is right for a first run and wrong for somebody who wants to choose,
which is what this adds.

**The bug this file is mostly about.** The first implementation read
`max_budget_gb` as *what the model requires* and graded fit against it.
It is a tier's **ceiling** — which machines the tier is aimed at — so
`qwen3:0.6b`, half a gigabyte, reported *does not fit* on a 9 GB budget,
because 9 is not `<= 3`. Fit is arithmetic on the download size;
recommendation is tier membership; they are two questions and
`TestFitIsArithmeticNotTierMembership` keeps them apart.
"""

from __future__ import annotations

import json

import pytest

from providers.model_manifest import GB, catalogue_for

#: A manifest with the same shape as the shipped one, small enough to
#: reason about. Written here rather than read from the bundle so these
#: tests do not change meaning when the real list is refreshed.
MANIFEST = {
    "generated": "2026-09-24",
    "tiers": [
        {"max_budget_gb": 3, "models": [
            {"name": "tiny:0.6b", "size_bytes": 500_000_000, "why": "smallest"},
            {"name": "small:4b", "size_bytes": 2_500_000_000, "why": "if affordable"},
        ]},
        # `small:4b` is in both tiers on purpose -- the real manifest does
        # the same, listing a smaller model again as the quicker option --
        # which is what `test_a_model_in_two_tiers_is_listed_once` covers.
        {"max_budget_gb": 9, "models": [
            {"name": "middle:8b", "size_bytes": 5_200_000_000, "why": "the usual choice"},
            {"name": "small:4b", "size_bytes": 2_500_000_000, "why": "quicker"},
        ]},
        {"max_budget_gb": None, "models": [
            {"name": "large:27b", "size_bytes": 18_000_000_000, "why": "for depth"},
        ]},
    ],
}


@pytest.fixture
def manifest(tmp_path):
    path = tmp_path / "models.manifest.json"
    path.write_text(json.dumps(MANIFEST), encoding="utf-8")
    return str(path)


def names(entries):
    return [e.model.name for e in entries]


class TestWhatIsListed:
    def test_every_model_appears_not_only_this_machines_tier(self, manifest):
        found = catalogue_for(9 * GB, path=manifest)
        assert set(names(found)) == {"tiny:0.6b", "small:4b", "middle:8b", "large:27b"}

    def test_a_model_in_two_tiers_is_listed_once(self, manifest):
        """`small:4b` is in the 3 GB tier and again in the 9 GB one. One
        name is one thing to download."""
        found = catalogue_for(9 * GB, path=manifest)
        assert names(found).count("small:4b") == 1

    def test_smallest_first(self, manifest):
        """Read by somebody deciding what to spend a download on. The
        cheapest option is the one most likely to be taken on a metered
        connection."""
        assert names(catalogue_for(9 * GB, path=manifest)) == [
            "tiny:0.6b", "small:4b", "middle:8b", "large:27b",
        ]

    def test_a_missing_manifest_is_an_empty_list_not_a_crash(self, tmp_path):
        """A packaging mistake must cost a recommendation, never the
        screen."""
        assert catalogue_for(9 * GB, path=str(tmp_path / "gone.json")) == []

    def test_a_model_with_no_size_is_left_out(self, tmp_path):
        """An offer whose cost is unstated is the one thing this must not
        be — the same rule `_models_in` already applies."""
        path = tmp_path / "m.json"
        path.write_text(json.dumps({
            "generated": "x",
            "tiers": [{"max_budget_gb": None, "models": [
                {"name": "priceless:1b", "why": "no size"},
                {"name": "honest:1b", "size_bytes": 1_000_000_000, "why": "has one"},
            ]}],
        }), encoding="utf-8")
        assert names(catalogue_for(9 * GB, path=str(path))) == ["honest:1b"]


class TestFitIsArithmeticNotTierMembership:
    """The bug this file exists for.

    `max_budget_gb` is a tier's ceiling — which machines it is *aimed at* —
    not what its models require. Read as a requirement it greys out every
    small model on a capable machine, which is exactly backwards.
    """

    def test_a_tiny_model_fits_a_large_machine(self, manifest):
        found = {e.model.name: e for e in catalogue_for(9 * GB, path=manifest)}
        assert found["tiny:0.6b"].fits is True

    def test_but_it_is_not_what_that_machine_is_told_to_download(self, manifest):
        """Fits and recommended are different answers, and the row shows
        both.

        `tiny:0.6b` runs anywhere and is in nobody's tier above 3 GB, so a
        9 GB machine sees it as available and not suggested. That pair is
        the whole reason the browser needs two marks instead of one.
        """
        found = {e.model.name: e for e in catalogue_for(9 * GB, path=manifest)}
        assert found["tiny:0.6b"].fits is True
        assert found["tiny:0.6b"].recommended is False
        assert found["middle:8b"].recommended is True

    def test_a_model_larger_than_the_budget_does_not_fit(self, manifest):
        found = {e.model.name: e for e in catalogue_for(9 * GB, path=manifest)}
        assert found["large:27b"].fits is False

    def test_a_small_machine_fits_only_the_small_one(self, manifest):
        found = {e.model.name: e for e in catalogue_for(3 * GB, path=manifest)}
        assert found["tiny:0.6b"].fits is True
        assert found["small:4b"].fits is True
        assert found["middle:8b"].fits is False

    def test_the_recommendation_matches_what_first_run_would_offer(self, manifest):
        """Marked from `recommend_for` rather than recomputed, so the badge
        cannot disagree with the offer the first-run screen makes."""
        from providers.model_manifest import recommend_for

        offered = {r.name for r in recommend_for(9 * GB, path=manifest)}
        marked = {e.model.name for e in catalogue_for(9 * GB, path=manifest) if e.recommended}
        assert marked == offered


class TestAnUnmeasurableMachine:
    """Apple and DirectML report no VRAM, and `hardware.py` returns `None`
    rather than zero for exactly this reason. `fits` inherits that."""

    def test_fit_is_unknown_rather_than_false(self, manifest):
        for entry in catalogue_for(None, path=manifest):
            assert entry.fits is None, entry.model.name

    def test_which_is_not_the_same_as_nothing_fitting(self, manifest):
        """Rendering `None` as "does not fit" would grey out the whole
        catalogue on a Mac; as "fits" it would promise something nobody
        measured. The third value is the point."""
        found = catalogue_for(None, path=manifest)
        assert all(e.fits is not False for e in found)

    def test_the_smallest_tier_is_still_recommended(self, manifest):
        """`recommend_for` takes the first tier on an unmeasured machine —
        the conservative, honest choice."""
        marked = {e.model.name for e in catalogue_for(None, path=manifest) if e.recommended}
        assert marked == {"tiny:0.6b", "small:4b"}


class TestWhatIsAlreadyHere:
    def test_an_installed_model_is_marked(self, manifest):
        found = {e.model.name: e for e in catalogue_for(
            9 * GB, installed=["middle:8b"], path=manifest
        )}
        assert found["middle:8b"].installed is True
        assert found["tiny:0.6b"].installed is False

    def test_the_row_carries_everything_the_browser_draws(self, manifest):
        row = catalogue_for(9 * GB, path=manifest)[0].to_dict()
        for key in ("name", "size_bytes", "why", "generated", "fits", "recommended", "installed"):
            assert key in row, f"{key} missing from the catalogue row"

    def test_the_manifest_date_rides_on_every_row(self, manifest):
        """`CLAUDE.md` asks for it to be visible: a recommendation is only
        as current as the list it came from."""
        for entry in catalogue_for(9 * GB, path=manifest):
            assert entry.model.generated == "2026-09-24"


class TestDownloadingAChosenModel:
    """The guarantee `/pull` was protecting, kept while allowing a choice.

    It refused a name in the body because *"a name in a request body would
    be a second source of truth ... the user would be charged gigabytes for
    a model nobody offered."* The invariant was never "no name" — it was
    that the thing downloaded is the thing quoted. A name that only
    *selects a manifest row* keeps that.
    """

    @pytest.fixture()
    def client(self):
        from fastapi.testclient import TestClient

        import main

        return TestClient(main.app)

    def test_a_model_not_in_the_manifest_is_refused(self, client):
        response = client.post("/providers/pull", json={"name": "evil/backdoor:latest"})
        assert response.status_code == 400
        assert "own list" in response.json()["detail"]

    def test_the_refusal_names_what_was_asked_for(self, client):
        response = client.post("/providers/pull", json={"name": "nope:1b"})
        assert "nope:1b" in response.json()["detail"]

    def test_the_catalogue_route_answers(self, client):
        response = client.get("/providers/recommendations")
        assert response.status_code == 200, response.text
        body = response.json()
        assert isinstance(body["models"], list)
        assert "budget_bytes" in body

    def test_the_route_reports_an_unmeasured_budget_as_null(self, client):
        """Not zero. A budget of 0 reads as "no room" on a machine nobody
        measured — the false zero `vram_bytes` already refuses."""
        budget = client.get("/providers/recommendations").json()["budget_bytes"]
        assert budget is None or budget > 0

    def test_every_row_the_route_sends_is_from_the_manifest(self, client):
        """The browser cannot offer something the manifest does not, which
        is what makes the 400 above a complete defence rather than a
        filter somebody could route around."""
        from providers.model_manifest import catalogue_for as real

        served = {m["name"] for m in client.get("/providers/recommendations").json()["models"]}
        known = {e.model.name for e in real(None)} | {e.model.name for e in real(9 * GB)}
        assert served <= known


class TestCapabilities:
    """Badges are claims, and a claim needs evidence.

    Empty means "the list does not say", never "cannot". A made-up absence
    would be a badge-shaped fact nobody measured.
    """

    def _write(self, tmp_path, entry):
        path = tmp_path / "m.json"
        path.write_text(json.dumps({
            "generated": "x",
            "tiers": [{"max_budget_gb": None, "models": [entry]}],
        }), encoding="utf-8")
        return str(path)

    def test_a_stated_capability_comes_through(self, tmp_path):
        path = self._write(tmp_path, {
            "name": "a:1b", "size_bytes": 1, "why": "w", "capabilities": ["vision", "tools"],
        })
        assert catalogue_for(9 * GB, path=path)[0].model.capabilities == ("vision", "tools")

    def test_an_entry_that_states_none_has_none(self, tmp_path):
        path = self._write(tmp_path, {"name": "a:1b", "size_bytes": 1, "why": "w"})
        assert catalogue_for(9 * GB, path=path)[0].model.capabilities == ()

    def test_a_word_outside_the_vocabulary_is_dropped(self, tmp_path):
        """A typo costs a badge, not a screen that renders whatever it was handed."""
        path = self._write(tmp_path, {
            "name": "a:1b", "size_bytes": 1, "why": "w", "capabilities": ["vision", "telepathy"],
        })
        assert catalogue_for(9 * GB, path=path)[0].model.capabilities == ("vision",)

    def test_it_reaches_the_row_the_browser_renders(self, tmp_path):
        path = self._write(tmp_path, {
            "name": "a:1b", "size_bytes": 1, "why": "w", "capabilities": ["thinking"],
        })
        assert catalogue_for(9 * GB, path=path)[0].to_dict()["capabilities"] == ["thinking"]


class TestTabbyBuildsAreListedAndGradedNotFetched:
    """The manifest knew Ollama tags only, so a TabbyAPI model was invisible to
    the browser and Zaram could not recommend a single model that its owner
    could load. EXL3 builds are revisions of a repository, not tags: Zaram lists
    and grades them, says whether they are here, and gives the command -- but
    never fetches them, because TabbyAPI's model folder is its own setting.
    """

    @staticmethod
    def _manifest(tmp_path, entries):
        path = tmp_path / "m.json"
        path.write_text(json.dumps({
            "generated": "2026-10-04",
            "tiers": [{"max_budget_gb": None, "models": [
                {"name": "small:4b", "size_bytes": 2_500_000_000, "why": "ollama one"},
            ]}],
            "tabby": entries,
        }), encoding="utf-8")
        return str(path)

    ENTRY = {
        "name": "Big-27B-exl3-2.20bpw", "repo": "someone/Big-27B-exl3", "revision": "2.20bpw",
        "parameters_b": 27, "bits_per_weight": 2.2, "why": "squeezed",
        "capabilities": ["vision"],
    }

    def test_size_is_arithmetic(self, tmp_path):
        path = self._manifest(tmp_path, [self.ENTRY])
        entry = {e.model.name: e for e in catalogue_for(9 * GB, path=path)}["Big-27B-exl3-2.20bpw"]
        assert entry.model.size_bytes == int(27e9 * 2.2 / 8)

    def test_it_agrees_with_the_size_derived_from_the_served_name(self, tmp_path):
        """A build listed here and the same build served must agree about how
        big it is, or the browser and the residency gate contradict each other."""
        from providers.discoverers.openai_compat import size_from_id

        path = self._manifest(tmp_path, [self.ENTRY])
        listed = {e.model.name: e for e in catalogue_for(9 * GB, path=path)}["Big-27B-exl3-2.20bpw"]
        assert listed.model.size_bytes == size_from_id(listed.model.name)

    def test_it_is_graded_against_the_budget_like_any_other(self, tmp_path):
        path = self._manifest(tmp_path, [self.ENTRY])
        assert {e.model.name: e.fits for e in catalogue_for(9 * GB, path=path)}["Big-27B-exl3-2.20bpw"] is True
        assert {e.model.name: e.fits for e in catalogue_for(6 * GB, path=path)}["Big-27B-exl3-2.20bpw"] is False
        assert {e.model.name: e.fits for e in catalogue_for(None, path=path)}["Big-27B-exl3-2.20bpw"] is None

    def test_it_is_never_the_first_run_recommendation(self, tmp_path):
        """`recommended` means what first run would offer, and first run offers
        only what Zaram can fetch."""
        from providers.model_manifest import recommend_for

        path = self._manifest(tmp_path, [self.ENTRY])
        assert all(e.recommended is False for e in catalogue_for(20 * GB, path=path) if e.model.runtime == "tabby")
        assert "Big-27B-exl3-2.20bpw" not in [r.name for r in recommend_for(20 * GB, path=path)]

    def test_it_says_what_serves_it_and_gives_the_command(self, tmp_path):
        path = self._manifest(tmp_path, [self.ENTRY])
        row = {e.model.name: e for e in catalogue_for(9 * GB, path=path)}["Big-27B-exl3-2.20bpw"].to_dict()
        assert row["runtime"] == "tabby"
        assert row["install_command"].startswith("hf download someone/Big-27B-exl3 --revision 2.20bpw")
        assert "<your TabbyAPI models folder>" in row["install_command"]  # said, not guessed

    def test_an_ollama_row_has_no_command(self, tmp_path):
        path = self._manifest(tmp_path, [self.ENTRY])
        row = {e.model.name: e for e in catalogue_for(9 * GB, path=path)}["small:4b"].to_dict()
        assert row["runtime"] == "ollama"
        assert "install_command" not in row

    def test_installed_is_recognised_by_the_name_the_server_reports(self, tmp_path):
        path = self._manifest(tmp_path, [self.ENTRY])
        here = {e.model.name: e for e in catalogue_for(9 * GB, installed=["Big-27B-exl3-2.20bpw"], path=path)}
        assert here["Big-27B-exl3-2.20bpw"].installed is True

    @pytest.mark.parametrize("broken", [
        {"name": "x", "bits_per_weight": 2.0},                   # no parameter count
        {"name": "x", "parameters_b": 27},                       # no precision
        {"name": "", "parameters_b": 27, "bits_per_weight": 2},  # no name
        {"name": "x", "parameters_b": 0, "bits_per_weight": 2},  # a size of nothing
        "not even a dict",
    ])
    def test_an_entry_that_cannot_state_its_size_is_left_out(self, tmp_path, broken):
        path = self._manifest(tmp_path, [broken])
        assert [e.model.name for e in catalogue_for(9 * GB, path=path)] == ["small:4b"]

    def test_the_shipped_manifest_has_the_build_this_machine_runs(self):
        names = [e.model.name for e in catalogue_for(9 * GB) if e.model.runtime == "tabby"]
        assert "Qwen3.8-27B-exl3-2.20bpw" in names

    def test_the_installed_names_include_what_an_openai_compatible_server_calls_it(self):
        from types import SimpleNamespace

        from providers.api import _installed_names

        served = SimpleNamespace(
            name="", display_name="Qwen3.8-27B-exl3-2.20bpw",
            metadata={"raw_id": "Qwen3.8-27B-exl3-2.20bpw"},
        )
        ollama = SimpleNamespace(name="qwen3:8b", display_name="qwen3:8b", metadata={})
        assert _installed_names([served, ollama]) == ["Qwen3.8-27B-exl3-2.20bpw", "qwen3:8b"]


class TestThePullRouteRefusesWhatOllamaCannotFetch:
    def test_a_tabby_build_is_a_400_and_nothing_is_logged(self, monkeypatch):
        from fastapi.testclient import TestClient
        from types import SimpleNamespace

        import core.egress as egress_pkg

        logged = []
        monkeypatch.setattr(
            egress_pkg, "get_gate",
            lambda: SimpleNamespace(log=SimpleNamespace(append=lambda **k: logged.append(k))),
            raising=False,
        )
        from main import app

        response = TestClient(app).post("/providers/pull", json={"name": "Qwen3.8-27B-exl3-2.20bpw"})
        assert response.status_code == 400
        assert "TabbyAPI" in response.json()["detail"]
        assert logged == []
