"""The route behind the Save button, exercised as the interface exercises it.

`test_an_unkept_image_clears_itself.py` covers the store and the service. This
covers the two things only a request can show: that the endpoint is **mounted**
— this repository has found fifteen complete, tested, unreachable subsystems,
so a green service test proves nothing about reachability — and that the JSON
the card renders actually carries `staged` and `expires_at`.

The card decides what to draw from those two fields alone. If they were absent
or wrong, every test in the other file would still pass and the user would go
on seeing "saved to your output folder" over a file that was not saved, which
is the exact complaint this work started from.
"""

from __future__ import annotations

import time

import pytest
from starlette.testclient import TestClient

import main
from artifacts.records import ArtifactRecords
from artifacts.service import ArtifactService
from artifacts.staging import RETENTION_SECONDS, StagingStore
from artifacts.store import ArtifactStore

PNG = bytes.fromhex("89504e470d0a1a0a")


@pytest.fixture
def client(tmp_path, monkeypatch):
    """The real app, with its artifact service pointed at a temporary disk.

    Monkeypatching the module global rather than building a second app: the
    routes close over `main.artifact_service`, and an app assembled another way
    would be testing a different object than the one that serves the user.
    """
    service = ArtifactService(
        ArtifactRecords(str(tmp_path / "artifacts.db")),
        ArtifactStore(tmp_path / "generated"),
        StagingStore(tmp_path / "staged"),
    )
    monkeypatch.setattr(main, "artifact_service", service)
    with TestClient(main.app) as client:
        client.service = service  # type: ignore[attr-defined]
        yield client


class TestWhatTheCardIsToldAboutAnImage:
    def test_a_generated_image_is_reported_as_staged(self, client):
        artifact = client.service.create_image(title="Blue", png=PNG)

        body = client.get(f"/artifacts/{artifact.id}").json()
        payload = body.get("artifact", body)

        assert payload["staged"] is True
        assert payload["expires_at"] is not None

    def test_the_window_it_reports_is_the_one_that_will_be_enforced(self, client):
        """The card counts down to `expires_at` and the sweeper acts on the
        file's mtime. If those disagreed the card would count down to a moment
        nothing happens, or the file would go early — and early is the one that
        reads as Zaram losing work."""
        artifact = client.service.create_image(title="Blue", png=PNG)

        body = client.get(f"/artifacts/{artifact.id}").json()
        expires_at = (body.get("artifact", body))["expires_at"]

        assert client.service.staging.sweep(now=expires_at - 1) == []
        assert client.service.staging.sweep(now=expires_at + 1) != []

    def test_the_window_is_about_a_week_away(self, client):
        artifact = client.service.create_image(title="Blue", png=PNG)

        body = client.get(f"/artifacts/{artifact.id}").json()
        expires_at = (body.get("artifact", body))["expires_at"]

        assert RETENTION_SECONDS - 60 < expires_at - time.time() <= RETENTION_SECONDS

    def test_a_document_is_never_reported_as_staged(self, client):
        artifact = client.service.create_document(title="Notes", blocks=[])

        body = client.get(f"/artifacts/{artifact.id}").json()
        payload = body.get("artifact", body)

        assert payload["staged"] is False
        assert payload["expires_at"] is None


class TestPressingSave:
    def test_the_route_is_mounted(self, client):
        """Not a formality. A complete, tested, unreachable feature is this
        repository's most common defect, and a keep endpoint nothing can call
        would leave the button doing nothing at all."""
        artifact = client.service.create_image(title="Blue", png=PNG)

        assert client.post(f"/artifacts/{artifact.id}/keep").status_code == 200

    def test_the_file_reaches_the_output_folder(self, client):
        artifact = client.service.create_image(title="Blue", png=PNG)

        client.post(f"/artifacts/{artifact.id}/keep")

        assert [p.name for p in client.service.store.list_files()] == ["blue.png"]

    def test_the_response_says_it_is_no_longer_staged(self, client):
        """What the card re-renders from. Left as `true`, the button would stay
        on screen over a file that is already saved."""
        artifact = client.service.create_image(title="Blue", png=PNG)

        payload = client.post(f"/artifacts/{artifact.id}/keep").json()["artifact"]

        assert payload["staged"] is False
        assert payload["expires_at"] is None
        assert payload["exists"] is True

    def test_the_response_carries_the_name_the_file_actually_got(self, client):
        """The output folder increments on collision, so the kept name can
        differ from the staged one. A card that went on showing the old name
        would be naming a file nobody has."""
        client.service.store.write_new("blue.png", b"something else")
        artifact = client.service.create_image(title="Blue", png=PNG)

        payload = client.post(f"/artifacts/{artifact.id}/keep").json()["artifact"]

        assert payload["filename"] == "blue-2.png"

    def test_pressing_it_twice_is_not_an_error(self, client):
        artifact = client.service.create_image(title="Blue", png=PNG)
        client.post(f"/artifacts/{artifact.id}/keep")

        second = client.post(f"/artifacts/{artifact.id}/keep")

        assert second.status_code == 200
        assert len(client.service.store.list_files()) == 1, "the file was saved twice"

    def test_an_unknown_artifact_is_refused(self, client):
        assert client.post("/artifacts/does-not-exist/keep").status_code == 404

    def test_a_kept_image_survives_a_sweep(self, client):
        """End to end, and the property the whole design is built around: the
        output folder never loses a file."""
        artifact = client.service.create_image(title="Blue", png=PNG)
        client.post(f"/artifacts/{artifact.id}/keep")

        client.service.staging.sweep(now=time.time() + RETENTION_SECONDS + 1)

        assert client.service.store.read("blue.png") == PNG
        assert client.get(f"/artifacts/{artifact.id}").status_code == 200
