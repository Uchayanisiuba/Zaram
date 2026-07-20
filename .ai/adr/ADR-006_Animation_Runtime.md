# ADR-006: Animation Runtime
**Status:** Accepted
**Context:** State machines alone feel robotic. Continuous parameters are needed for organic motion.
**Decision:** Implement Animation Runtime to translate discrete states + continuous parameters into procedural motion using the Emotion Engine and Living Rhythm.
**Consequences:** Requires GPU-accelerated interpolation to maintain 60fps.