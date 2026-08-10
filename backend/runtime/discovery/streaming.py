# backend/runtime/discovery/streaming.py
from __future__ import annotations

from collections.abc import AsyncIterator

from .contracts import (
    DiscoveryContext,
    DiscoveryProvider,
    DiscoveryRequest,
    DiscoveryResult,
    StreamingDiscoveryResult,
)


class StreamingDiscovery:
    """Supports incremental discovery with streaming results."""

    async def stream_discover(
        self,
        provider: DiscoveryProvider,
        request: DiscoveryRequest,
        context: DiscoveryContext,
    ) -> AsyncIterator[StreamingDiscoveryResult]:
        if request.stream_callback is None:
            yield StreamingDiscoveryResult(
                result=DiscoveryResult(
                    content="",
                    summary="No stream callback configured.",
                    metadata=DiscoveryResult.__dataclass_fields__["metadata"].type if hasattr(DiscoveryResult.__dataclass_fields__.get("metadata"), "type") else None,
                ),
                is_final=True,
                provider_id=provider.get_provider_id(),
                sequence=0,
            )
            return

        sequence = 0
        try:
            results = await provider.discover(request, context)
            for r in results:
                sequence += 1
                stream_result = StreamingDiscoveryResult(
                    result=r,
                    is_final=(sequence == len(results)),
                    provider_id=provider.get_provider_id(),
                    sequence=sequence,
                )
                request.stream_callback(r)
                yield stream_result
        except Exception:
            yield StreamingDiscoveryResult(
                result=DiscoveryResult(
                    content="",
                    summary="Streaming provider failed.",
                    metadata=DiscoveryResult.__dataclass_fields__["metadata"].type if hasattr(DiscoveryResult.__dataclass_fields__.get("metadata"), "type") else None,
                ),
                is_final=True,
                provider_id=provider.get_provider_id(),
                sequence=sequence,
            )
