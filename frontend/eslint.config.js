import { defineConfig, globalIgnores } from 'eslint/config'
import globals from 'globals'
import tsParser from '@typescript-eslint/parser'
import tsPlugin from '@typescript-eslint/eslint-plugin'

/**
 * Lint, configured so it can actually pass.
 *
 * **The 157 warnings were the config, not the code.** `npm run lint` runs with
 * `--max-warnings 0` and had been unable to pass for five sessions, which the
 * milestone file kept recording as "a gate nobody can run". Nobody read the
 * warnings, because a permanently failing gate teaches you not to. All 157
 * were false:
 *
 * * **`no-undef` on TypeScript.** Core ESLint has no type information, so it
 *   reported `RequestInit`, `ResponseInit` and `JSX` — types, not values — as
 *   undefined globals, plus 28 uses of `React` in files relying on the
 *   automatic JSX runtime, where importing it would be the actual mistake.
 *   typescript-eslint disables this rule outright for TS, because `tsc` checks
 *   the same thing with the types in hand and `npm run typecheck` is clean.
 *
 * * **Core `no-unused-vars` on TypeScript.** It cannot see that an interface,
 *   a type alias or a type-only import is used, so 114 of the warnings were
 *   about symbols that are used, in type positions it does not parse.
 *
 * The replacement rules are typescript-eslint's, which understand both. This
 * is a repair, not a threshold change: a lint run that reports 157 false
 * positives is worse than none, because it hides the true ones — the whole
 * argument this codebase already makes about tests that assert nothing.
 *
 * The leading-underscore escape is deliberate and conventional: a deliberately
 * unused binding says so in its name, which a reader can see and a suppression
 * comment does not.
 */
export default defineConfig([
  globalIgnores(['dist', 'legacy', 'scripts/drive-shots']),
  {
    files: ['**/*.{js,jsx,ts,tsx}'],
    languageOptions: {
      globals: { ...globals.browser, ...globals.node },
      parser: tsParser,
      parserOptions: {
        ecmaVersion: 2022,
        sourceType: 'module',
        ecmaFeatures: { jsx: true },
      },
    },
    plugins: { '@typescript-eslint': tsPlugin },
    rules: {
      // TypeScript resolves identifiers with the types available; ESLint here
      // does not. Leaving this on produced only false positives.
      'no-undef': 'off',
      'no-unused-vars': 'off',
      '@typescript-eslint/no-unused-vars': [
        'warn',
        {
          argsIgnorePattern: '^_',
          varsIgnorePattern: '^_',
          caughtErrorsIgnorePattern: '^_',
          // A destructured rest is how a prop is deliberately dropped —
          // `const { onClick, ...rest } = props` — and flagging it would push
          // authors toward a suppression comment instead.
          ignoreRestSiblings: true,
        },
      ],
    },
  },
])
