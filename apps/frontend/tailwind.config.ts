import type { Config } from "tailwindcss";

// PolyHire design system — "candidate galaxy" / observatory visual language.
// See §10.2 of the PRD. Tokens are referenced via Tailwind utilities
// (e.g. `bg-void`, `text-starlight`) across the app.
export default {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        void: "#0B1026",
        surface: "#161B33",
        "surface-2": "#1E2444",
        starlight: "#E8A33D",
        primary: "#F5F1E8",
        trust: "#4FD1C5",
        alert: "#E8604C",
        gridline: "#2A2F4D",
      },
      fontFamily: {
        display: ["Fraunces", "serif"],
        body: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
      animation: {
        "pulse-slow": "pulse 3s ease-in-out infinite",
        "spin-slow": "spin 12s linear infinite",
        "fade-in": "fadeIn 0.4s ease-out",
      },
      keyframes: {
        fadeIn: {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
    },
  },
  plugins: [],
} satisfies Config;
