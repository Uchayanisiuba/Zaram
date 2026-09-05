"""Staging: what is generated waits, what is kept is saved, what is not clears.

Asked for by the maintainer on 4 September 2026, looking at an image card that
read *"saved to your output folder"* -- **should the user not choose what to
save?** They should, and the reason they could not is recorded in
`artifacts/staging.py`: the no-delete guarantee was designed for documents, and
the image flow generates discards by design.

The property every test here is really defending: **the output folder never
loses a file.** Staging may expire its own contents, because staging never told
the user anything was saved. Those two sentences are the whole design, and the
tests are arranged so that breaking either one fails.
"""

from __future__ import annotations

import time

import pytest

from artifacts.staging import (
    DEFAULT_STAGING_DIRNAME,
    RETENTION_SECONDS,
    StagingStore,
    default_staging_root,
)
from artifacts.records import ArtifactRecords
from artifacts.service import ArtifactService
from artifacts.store import ArtifactStore


@pytest.fixture
def stores(tmp_path):
    """A staging area and an output folder, as the app has one of each."""
    return (
        StagingStore(tmp_path / "staged"),
        ArtifactStore(tmp_path / "generated"),
    )


class TestNothingReachesTheOutputFolderUnasked:
    def test_a_staged_file_is_not_in_the_output_folder(self, stores):
        staging, output = stores
        staging.write_new("blue.png", b"pixels")

        assert output.list_files() == [], (
            "the whole point: a generated image is not saved anywhere the user "
            "has to clean up until they say so"
        )

    def test_the_staging_area_is_not_inside_the_output_folder(self, tmp_path, monkeypatch):
        """Inside it, every listing of the output folder -- the user's own file
        manager included -- would show a directory of rejects."""
        monkeypatch.setenv("ZARAM_OUTPUT_DIR", str(tmp_path / "generated"))
        monkeypatch.delenv("ZARAM_STAGING_DIR", raising=False)

        staged = default_staging_root()

        assert staged.name == DEFAULT_STAGING_DIRNAME
        assert (tmp_path / "generated") not in staged.parents
        assert staged.parent == tmp_path


class TestKeepingOne:
    def test_it_lands_in_the_output_folder(self, stores):
        staging, output = stores
        path = staging.write_new("blue.png", b"pixels")

        kept = staging.promote(path, output)

        assert kept.parent == output.root
        assert kept.read_bytes() == b"pixels"

    def test_the_staged_copy_is_gone(self, stores):
        staging, output = stores
        path = staging.write_new("blue.png", b"pixels")

        staging.promote(path, output)

        assert not path.exists()
        assert staging.root.exists(), "the directory itself stays"

    def test_keeping_one_of_four_leaves_the_other_three_staged(self, stores):
        """The batch case this exists for. The three not chosen are not
        deleted on the spot -- they wait out their window, because 'I picked
        the wrong one' arrives about a minute later."""
        staging, output = stores
        paths = [staging.write_new(f"option-{n}.png", b"x") for n in range(4)]

        staging.promote(paths[1], output)

        assert [p.name for p in output.list_files()] == ["option-1.png"]
        assert sorted(p.name for p in staging.root.iterdir()) == [
            "option-0.png",
            "option-2.png",
            "option-3.png",
        ]

    def test_a_name_that_collides_increments_rather_than_replacing(self, stores):
        """Promotion goes through `write_new` like every other caller, so the
        output folder's no-overwrite guarantee covers this path too."""
        staging, output = stores
        output.write_new("blue.png", b"the first one")
        path = staging.write_new("blue.png", b"the second one")

        kept = staging.promote(path, output)

        assert kept.name == "blue-2.png"
        assert output.read("blue.png") == b"the first one", "an existing file was replaced"


class TestClearingWhatNobodyKept:
    def test_a_fresh_file_is_not_swept(self, stores):
        staging, _ = stores
        path = staging.write_new("blue.png", b"pixels")

        assert staging.sweep() == []
        assert path.exists()

    def test_a_file_past_its_window_is_removed(self, stores):
        staging, _ = stores
        path = staging.write_new("blue.png", b"pixels")

        removed = staging.sweep(now=time.time() + RETENTION_SECONDS + 1)

        assert removed == [path]
        assert not path.exists()

    def test_the_window_is_the_one_the_card_shows(self, stores):
        """`expires_at` is what the interface renders, and `sweep` is what
        acts. If they disagreed the card would count down to a moment nothing
        happens, or a file would vanish early -- and early is the one that
        looks like Zaram losing work."""
        staging, _ = stores
        path = staging.write_new("blue.png", b"pixels")

        due = staging.expires_at(path)

        assert staging.sweep(now=due - 1) == []
        assert staging.sweep(now=due + 1) == [path]

    def test_sweeping_never_touches_the_output_folder(self, stores):
        """The assertion the whole module is built around."""
        staging, output = stores
        kept = output.write_new("invoice.pdf", b"an invoice")
        staging.write_new("blue.png", b"pixels")

        staging.sweep(now=time.time() + RETENTION_SECONDS + 1)

        assert kept.exists()
        assert output.read("invoice.pdf") == b"an invoice"

    def test_a_kept_file_cannot_be_swept_afterwards(self, stores):
        """Promotion is what takes a file out of reach of expiry. If keeping
        left anything behind that `sweep` still matched, the user's chosen
        image would disappear a week later."""
        staging, output = stores
        path = staging.write_new("blue.png", b"pixels")
        kept = staging.promote(path, output)

        staging.sweep(now=time.time() + RETENTION_SECONDS + 1)

        assert kept.exists()


class TestTellingStagedFromKept:
    def test_a_staged_path_is_recognised(self, stores):
        staging, _ = stores
        assert staging.is_staged(staging.write_new("blue.png", b"x"))

    def test_an_output_path_is_not(self, stores):
        """What gates the keep endpoint. Wrong here, and a request naming a
        path in the output folder would have that file moved and its original
        unlinked -- a delete, through the one door that must not have one."""
        staging, output = stores
        assert not staging.is_staged(output.write_new("invoice.pdf", b"x"))

    def test_something_outside_both_is_not(self, stores, tmp_path):
        staging, _ = stores
        stray = tmp_path / "elsewhere.png"
        stray.write_bytes(b"x")

        assert not staging.is_staged(stray)


#: Enough bytes to be a PNG header. The exporter writes what it is given.
PNG = bytes.fromhex("89504e470d0a1a0a")


@pytest.fixture
def service(tmp_path):
    return ArtifactService(
        ArtifactRecords(str(tmp_path / "artifacts.db")),
        ArtifactStore(tmp_path / "generated"),
        StagingStore(tmp_path / "staged"),
    )


class TestWhichKindsWait:
    def test_an_image_is_staged_rather_than_saved(self, service):
        artifact = service.create_image(title="Blue", png=PNG)

        assert service.staging.is_staged(artifact.path)
        assert service.store.list_files() == [], "an image was saved without being asked for"

    def test_a_document_still_goes_straight_to_the_output_folder(self, service):
        """Unchanged, and deliberately. An invoice is asked for once, on
        purpose, and making the user confirm it is the dialog rule 7h refuses."""
        artifact = service.create_document(title="Notes", blocks=[])

        assert not service.staging.is_staged(artifact.path)
        assert [p.name for p in service.store.list_files()] == [artifact.filename]

    def test_a_service_built_without_staging_stages_nothing(self, tmp_path):
        """Every existing caller passes two arguments. They must go on writing
        to the output folder rather than to a directory that does not exist."""
        service = ArtifactService(
            ArtifactRecords(str(tmp_path / "a.db")), ArtifactStore(tmp_path / "generated")
        )

        artifact = service.create_image(title="Blue", png=PNG)

        assert [p.name for p in service.store.list_files()] == [artifact.filename]


class TestKeepingThroughTheService:
    def test_the_file_moves_and_the_record_follows(self, service):
        artifact = service.create_image(title="Blue", png=PNG)

        kept = service.keep(artifact.id)

        assert kept.path.endswith("blue.png")
        assert service.store.list_files()[0].name == "blue.png"
        assert service.records.get(artifact.id).path == kept.path, (
            "the record still points at the staged copy, which is now gone"
        )

    def test_it_is_the_same_artifact_not_a_copy(self, service):
        """Keeping must not lose where the picture came from. A new record
        would have a new id, and the conversation that produced it would no
        longer point anywhere."""
        artifact = service.create_image(title="Blue", png=PNG, conversation_id="c1")

        kept = service.keep(artifact.id)

        assert kept.id == artifact.id
        assert service.records.get(artifact.id).conversation_id == "c1"

    def test_clicking_twice_is_not_an_error(self, service):
        artifact = service.create_image(title="Blue", png=PNG)
        first = service.keep(artifact.id)

        assert service.keep(artifact.id).path == first.path

    def test_a_kept_image_is_not_reported_as_staged(self, service):
        artifact = service.create_image(title="Blue", png=PNG)
        kept = service.keep(artifact.id)

        assert not service.staging.is_staged(kept.path)

    def test_an_unknown_id_is_refused(self, service):
        with pytest.raises(KeyError):
            service.keep("nope")


class TestTheRecordGoesWithTheFile:
    def test_forgetting_by_path_removes_exactly_one(self, service):
        staged = service.create_image(title="Blue", png=PNG)
        other = service.create_image(title="Green", png=PNG)

        assert service.records.forget_at_path(staged.path) == 1

        assert service.records.get(staged.id) is None
        assert service.records.get(other.id) is not None

    def test_a_kept_files_record_is_untouched_by_a_sweep(self, service):
        """The end-to-end property. Keep one, sweep, and what the user chose is
        still in Work and still on disk."""
        kept_artifact = service.keep(service.create_image(title="Blue", png=PNG).id)
        dropped = service.create_image(title="Green", png=PNG)

        for gone in service.staging.sweep(now=time.time() + RETENTION_SECONDS + 1):
            service.records.forget_at_path(str(gone))

        assert service.records.get(kept_artifact.id) is not None
        assert service.store.read("blue.png") == PNG, "the kept image lost its bytes"
        assert service.records.get(dropped.id) is None
