import { describe, it, expect } from 'vitest';
import { pastedKey } from './pastedKey';

const NVIDIA_SAMPLE = `from openai import OpenAI

client = OpenAI(
  base_url = "https://integrate.api.nvidia.com/v1",
  api_key = "nvapi-abcDEF123_ghi-JKL456mno789PQRstu012VWXyz"
)

completion = client.chat.completions.create(
  model="nvidia/nemotron-3.5-lightning-30b-a3b",
  messages=[{"role":"user","content":"Write a limerick."}],
)`;

describe('the key out of whatever was pasted', () => {
  it('leaves a bare key exactly as it is', () => {
    expect(pastedKey('nvapi-abcDEF123_ghi-JKL456mno789PQRstu012VWXyz')).toEqual({
      key: 'nvapi-abcDEF123_ghi-JKL456mno789PQRstu012VWXyz',
      extracted: false,
    });
    expect(pastedKey('  sk-or-v1-0123456789abcdef0123456789abcdef  ').key).toBe(
      'sk-or-v1-0123456789abcdef0123456789abcdef',
    );
  });

  it("lifts the key out of a provider's code sample, and says so", () => {
    // build.nvidia.com's Copy button copies the whole snippet — 14 September 2026.
    expect(pastedKey(NVIDIA_SAMPLE)).toEqual({
      key: 'nvapi-abcDEF123_ghi-JKL456mno789PQRstu012VWXyz',
      extracted: true,
    });
  });

  it('prefers the assigned value over a longer token beside it', () => {
    const js = `const client = new OpenAI({ apiKey: "sk-proj-AAAAbbbbCCCCddddEEEEffff1234", baseURL: "https://api.openai.com/v1/some/very-long-path-segment-here" });`;
    expect(pastedKey(js).key).toBe('sk-proj-AAAAbbbbCCCCddddEEEEffff1234');
  });

  it('takes a key out of a curl header', () => {
    const curl = `curl https://api.groq.com/openai/v1/models -H "Authorization: Bearer gsk_0123456789abcdefghijklmnopqrstuv"`;
    expect(pastedKey(curl)).toEqual({ key: 'gsk_0123456789abcdefghijklmnopqrstuv', extracted: true });
  });

  it('does not invent a key where nothing looks like one', () => {
    const prose = 'paste your key here, it is on the keys page';
    expect(pastedKey(prose)).toEqual({ key: prose, extracted: false });
    expect(pastedKey('   ')).toEqual({ key: '', extracted: false });
  });

  it('does not mistake a URL for a key', () => {
    const url = 'https://openrouter.ai/settings/keys/abcdefghijklmnopqrstuvwxyz0123';
    expect(pastedKey(url).extracted).toBe(false);
  });
});
