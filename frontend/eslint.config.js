import { defineConfig, globalIgnores } from 'eslint/config'
import globals from 'globals'
import tsParser from '@typescript-eslint/parser'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{js,jsx,ts,tsx}'],
    languageOptions: {
      globals: globals.browser,
      parser: tsParser,
      parserOptions: {
        ecmaVersion: 2020,
        sourceType: 'module',
        ecmaFeatures: { jsx: true },
      },
    },
    rules: {
      'no-unused-vars': 'warn',
      'no-undef': 'warn',
    },
  },
])
