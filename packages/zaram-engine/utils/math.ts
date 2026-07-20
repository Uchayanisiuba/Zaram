export function perlinNoise(x: number): number {
  const xi = Math.floor(x)
  const xf = x - xi
  const u = xf * xf * (3 - 2 * xf)
  const a = pseudoRandom(xi)
  const b = pseudoRandom(xi + 1)
  return a + (b - a) * u
}

function pseudoRandom(x: number): number {
  const n = Math.sin(x * 12.9898 + 78.233) * 43758.5453
  return n - Math.floor(n)
}
