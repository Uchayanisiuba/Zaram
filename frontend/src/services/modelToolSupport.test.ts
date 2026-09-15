/**
 * The picker says when a model cannot be given tools.
 *
 * Added 15 September 2026, with the coworker work. `supports_tools` has been
 * on `ModelInfo` since the provider layer shipped — read from what Ollama
 * declares in a model's own capabilities, and stated for the OpenAI-compatible
 * and Anthropic paths — and **nothing in the interface read it**. So a person
 * could pick a model that cannot call a thing, ask for a task, and get a reply
 * saying the work was done with none of it done: the model has no channel to
 * call a tool and no way to say so.
 *
 * The rule this pins is the same one `fitsResident` and `dataPolicy` follow:
 * an unread signal is never a reassuring default. A backend that does not send
 * the field reads as "cannot", which costs a visible sentence when wrong — and
 * the other direction costs a task that silently does nothing.
 */
import { describe, it, expect } from 'vitest';
import { toDiscoveredModel } from './settingsClient';

describe('a model row and its tools', () => {
  it('believes the provider when it says the model takes tools', () => {
    expect(toDiscoveredModel({ id: 'ollama:qwen3:14b', supports_tools: true }).supportsTools).toBe(true);
  });

  it('believes it when it says the model does not', () => {
    expect(toDiscoveredModel({ id: 'ollama:llava:7b', supports_tools: false }).supportsTools).toBe(false);
  });

  it('reads a missing field as cannot, never as a quiet yes', () => {
    // An older backend, or a provider that does not say. The safe direction is
    // the one whose error is a sentence rather than a silent failure.
    expect(toDiscoveredModel({ id: 'ollama:old' }).supportsTools).toBe(false);
    expect(toDiscoveredModel({ id: 'ollama:odd', supports_tools: 'yes' }).supportsTools).toBe(false);
  });
});
