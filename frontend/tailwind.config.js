export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        // Paleta Industrial Refinado
        surface: {
          950: "#0a0a0b",
          900: "#111113",
          800: "#1a1a1f",
          700: "#242429",
          600: "#2e2e35",
        },
        amber: {
          400: "#fbbf24",
          500: "#f59e0b",
          600: "#d97706",
        },
        neutral: {
          100: "#f5f5f4",
          200: "#e7e5e4",
          400: "#a8a29e",
          500: "#78716c",
          600: "#57534e",
        }
      },
      fontFamily: {
        display: ["'DM Serif Display'", "serif"],
        body: ["'DM Sans'", "sans-serif"],
        mono: ["'JetBrains Mono'", "monospace"],
      },
    },
  },
  plugins: [],
}
