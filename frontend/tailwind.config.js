/** @type {import('tailwindcss').Config} */

/* The colours below map to CSS variables that `src/index.css` defines in
 * `oklch()`. They used to be wrapped as `hsl(var(--x))`, which is what shadcn
 * emits when its variables hold bare HSL channels — and this theme was moved to
 * oklch without unwrapping them.
 *
 * `hsl(oklch(...))` is not valid CSS. The custom property still accepted the
 * token stream, so nothing errored and the build stayed green; the declarations
 * that consumed it were dropped at substitution time instead. Two consequences
 * were live in the shipped stylesheet:
 *
 *   *{border-color:hsl(var(--border))}   — a global rule, so every element with
 *     a border width and no explicit colour fell back to `currentColor` and drew
 *     its border in the text colour rather than the intended grey.
 *
 *   .focus\:ring-accent:focus            — the composer's focus ring, the only
 *     one in the app, painted nothing at all.
 *
 * Unwrapped, the variables pass through as the colours they already are. Note
 * that a bare `var()` gives up Tailwind's `<alpha-value>` support, so opacity
 * modifiers (`border-border/50`) will not work on these; nothing uses one.
 *
 * There was also a `tailwind.config.ts` beside this file. Tailwind resolves
 * `.js` first, so it never loaded — deleted rather than left to look load-bearing.
 */
export default {
  darkMode: ["class"],
  content: [
    './pages/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
    './app/**/*.{ts,tsx}',
    './src/**/*.{ts,tsx}',
    './index.html',
  ],
  prefix: "",
  theme: {
    container: {
      center: true,
      padding: "2rem",
      screens: {
        "2xl": "1400px",
      },
    },
    extend: {
      colors: {
        border: "var(--border)",
        input: "var(--input)",
        ring: "var(--ring)",
        background: "var(--background)",
        foreground: "var(--foreground)",
        primary: {
          DEFAULT: "var(--primary)",
          foreground: "var(--primary-foreground)",
        },
        secondary: {
          DEFAULT: "var(--secondary)",
          foreground: "var(--secondary-foreground)",
        },
        destructive: {
          DEFAULT: "var(--destructive)",
          foreground: "var(--destructive-foreground)",
        },
        muted: {
          DEFAULT: "var(--muted)",
          foreground: "var(--muted-foreground)",
        },
        accent: {
          DEFAULT: "var(--accent)",
          foreground: "var(--accent-foreground)",
        },
        popover: {
          DEFAULT: "var(--popover)",
          foreground: "var(--popover-foreground)",
        },
        card: {
          DEFAULT: "var(--card)",
          foreground: "var(--card-foreground)",
        },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      keyframes: {
        "accordion-down": {
          from: { height: "0" },
          to: { height: "var(--radix-accordion-content-height)" },
        },
        "accordion-up": {
          from: { height: "var(--radix-accordion-content-height)" },
          to: { height: "0" },
        },
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
}