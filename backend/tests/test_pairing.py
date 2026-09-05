"""Linking a phone, and the four properties that make it safe.

This is the first authentication the API has ever had, so the tests are mostly
about what must *not* work: a reused QR, an expired one, a revoked phone, and a
stolen database.
"""

from __future__ import annotations

import pytest

from core.pairing import TOKEN_TTL_SECONDS, DeviceRegistry, PairingError

NOW = 1_770_000_000.0


@pytest.fixture
def registry() -> DeviceRegistry:
    return DeviceRegistry()


class TestLinkingADevice:
    def test_a_scanned_token_links_the_phone(self, registry):
        token = registry.issue_token(now=NOW)
        device, credential = registry.redeem(token, device_name="Uche's phone", now=NOW)

        assert device.name == "Uche's phone"
        assert device.is_active
        assert credential

    def test_the_credential_then_authenticates(self, registry):
        token = registry.issue_token(now=NOW)
        device, credential = registry.redeem(token, now=NOW)

        assert registry.verify(credential) is not None
        assert registry.verify(credential).id == device.id

    def test_an_unnamed_device_still_gets_a_label(self, registry):
        """A blank row in a linked-devices list is one nobody dares revoke."""
        token = registry.issue_token(now=NOW)
        device, _ = registry.redeem(token, device_name="   ", now=NOW)
        assert device.name == "Unnamed device"

    def test_each_pairing_produces_a_different_credential(self, registry):
        first, credential_one = registry.redeem(registry.issue_token(now=NOW), now=NOW)
        second, credential_two = registry.redeem(registry.issue_token(now=NOW), now=NOW)

        assert credential_one != credential_two
        assert first.id != second.id


class TestTokensAreSingleUse:
    def test_a_token_cannot_be_redeemed_twice(self, registry):
        """A QR photographed over someone's shoulder is worthless once the real
        phone has used it."""
        token = registry.issue_token(now=NOW)
        registry.redeem(token, now=NOW)

        with pytest.raises(PairingError):
            registry.redeem(token, now=NOW)

    def test_an_expired_token_is_refused(self, registry):
        token = registry.issue_token(now=NOW)
        with pytest.raises(PairingError):
            registry.redeem(token, now=NOW + TOKEN_TTL_SECONDS + 1)

    def test_a_token_is_valid_right_up_to_expiry(self, registry):
        token = registry.issue_token(now=NOW)
        device, _ = registry.redeem(token, now=NOW + TOKEN_TTL_SECONDS)
        assert device.is_active

    def test_an_invented_token_is_refused(self, registry):
        with pytest.raises(PairingError):
            registry.redeem("not-a-real-token", now=NOW)

    def test_used_and_unknown_tokens_fail_identically(self, registry):
        """Distinguishing them tells an attacker which guesses were once real."""
        token = registry.issue_token(now=NOW)
        registry.redeem(token, now=NOW)

        with pytest.raises(PairingError) as used:
            registry.redeem(token, now=NOW)
        with pytest.raises(PairingError) as unknown:
            registry.redeem("wrong", now=NOW)

        assert str(used.value) == str(unknown.value)


class TestSecretsAreNotStored:
    def test_the_credential_is_not_recoverable_from_the_registry(self, registry):
        """A stolen spine.db must not yield working credentials."""
        token = registry.issue_token(now=NOW)
        device, credential = registry.redeem(token, now=NOW)

        assert credential not in repr(registry._devices)
        assert device.credential_hash != credential

    def test_the_token_is_not_stored_in_clear_either(self, registry):
        """A pending token is a live grant of access to everything."""
        token = registry.issue_token(now=NOW)
        assert token not in repr(registry._pending)

    def test_a_device_serialises_with_no_credential_field_at_all(self, registry):
        """Not empty, not redacted — absent. A field that sometimes holds a
        secret is one that will eventually be logged."""
        device, credential = registry.redeem(registry.issue_token(now=NOW), now=NOW)
        payload = device.to_dict()

        assert "credential" not in payload
        assert "credential_hash" not in payload
        assert credential not in str(payload)


class TestRevocation:
    def test_a_revoked_device_stops_working_immediately(self, registry):
        device, credential = registry.redeem(registry.issue_token(now=NOW), now=NOW)
        assert registry.verify(credential) is not None

        assert registry.revoke(device.id) is True
        assert registry.verify(credential) is None

    def test_revoking_twice_reports_that_it_was_already_done(self, registry):
        device, _ = registry.redeem(registry.issue_token(now=NOW), now=NOW)
        assert registry.revoke(device.id) is True
        assert registry.revoke(device.id) is False

    def test_revoking_something_unknown_is_not_an_error(self, registry):
        assert registry.revoke("no-such-device") is False

    def test_the_record_of_a_revoked_device_is_kept(self, registry):
        """"Which devices have ever had access, and when did that stop" has to
        stay answerable."""
        device, _ = registry.redeem(registry.issue_token(now=NOW), now=NOW)
        registry.revoke(device.id, now=NOW + 500)

        listed = {d.id: d for d in registry.devices()}
        assert listed[device.id].revoked_at == NOW + 500

    def test_revoking_one_device_leaves_the_others_alone(self, registry):
        first, credential_one = registry.redeem(registry.issue_token(now=NOW), now=NOW)
        _, credential_two = registry.redeem(registry.issue_token(now=NOW), now=NOW)

        registry.revoke(first.id)

        assert registry.verify(credential_one) is None
        assert registry.verify(credential_two) is not None


class TestVerification:
    def test_an_unknown_credential_is_refused(self, registry):
        registry.redeem(registry.issue_token(now=NOW), now=NOW)
        assert registry.verify("some-other-value") is None

    def test_an_empty_credential_is_refused(self, registry):
        assert registry.verify("") is None
        assert registry.verify(None) is None  # type: ignore[arg-type]

    def test_verifying_updates_last_seen(self, registry):
        """The linked-devices list is only useful if "last seen" is true."""
        device, credential = registry.redeem(registry.issue_token(now=NOW), now=NOW)
        registry.verify(credential, now=NOW + 900)

        assert registry.devices()[0].last_seen == NOW + 900

    def test_verify_alone_is_enough_to_be_safe(self, registry):
        """Revoked returns None rather than an inactive device, so no caller
        has to remember to check `is_active` — forgetting that is how a
        revoked phone keeps working."""
        device, credential = registry.redeem(registry.issue_token(now=NOW), now=NOW)
        registry.revoke(device.id)
        assert registry.verify(credential) is None


class TestListingAndHousekeeping:
    def test_devices_are_listed_newest_first(self, registry):
        older, _ = registry.redeem(registry.issue_token(now=NOW), now=NOW)
        newer, _ = registry.redeem(registry.issue_token(now=NOW), now=NOW + 60)

        assert [d.id for d in registry.devices()] == [newer.id, older.id]

    def test_revoked_devices_can_be_filtered_out(self, registry):
        active, _ = registry.redeem(registry.issue_token(now=NOW), now=NOW)
        gone, _ = registry.redeem(registry.issue_token(now=NOW), now=NOW)
        registry.revoke(gone.id)

        assert [d.id for d in registry.devices(include_revoked=False)] == [active.id]

    def test_spent_and_expired_tokens_are_purged(self, registry):
        registry.issue_token(now=NOW)
        used = registry.issue_token(now=NOW)
        registry.redeem(used, now=NOW)

        assert registry.purge_expired_tokens(now=NOW + TOKEN_TTL_SECONDS + 1) == 2
        assert registry._pending == {}

    def test_purging_does_not_unlink_anything(self, registry):
        _, credential = registry.redeem(registry.issue_token(now=NOW), now=NOW)
        registry.purge_expired_tokens(now=NOW + 10_000)
        assert registry.verify(credential) is not None
