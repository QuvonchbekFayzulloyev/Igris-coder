/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // "Oq / Ko'k / Yashil / To'q yashil" from the brief, given concrete
        // values. bg/ink form the white base; blue is the interactive
        // accent; green/green-dark carry state (running/success/methodology).
        bg: "#FFFFFF",
        "bg-subtle": "#F6FAF8",
        "bg-inset": "#EEF3F1",
        border: "#E1E8E5",
        ink: "#11181C",
        "ink-muted": "#5B6B66",
        "ink-faint": "#8B9995",
        blue: {
          DEFAULT: "#1D5FD6",
          dim: "#E8F0FE",
          hover: "#154FB8",
        },
        green: {
          DEFAULT: "#1FA463",
          dim: "#E3F5EC",
          dark: "#0B4D33",
        },
        amber: {
          DEFAULT: "#B8790A",
          dim: "#FBF0DD",
        },
        red: {
          DEFAULT: "#C4432E",
          dim: "#FBEAE6",
        },
      },
      fontFamily: {
        // Windows-first: Segoe UI is the native Windows system font --
        // using it (not a web font) keeps the app feeling native and
        // needs no network font fetch to render offline.
        sans: [
          "Segoe UI Variable",
          "Segoe UI",
          "-apple-system",
          "Inter",
          "system-ui",
          "sans-serif",
        ],
        // Cascadia Code ships with Windows Terminal/VS -- fitting for a
        // tool whose whole premise is transparent, code-adjacent tooling.
        mono: [
          "Cascadia Code",
          "Cascadia Mono",
          "Consolas",
          "ui-monospace",
          "SFMono-Regular",
          "monospace",
        ],
      },
      fontSize: {
        "2xs": ["0.6875rem", { lineHeight: "1rem" }],
      },
      animation: {
        "pulse-soft": "pulse-soft 1.6s ease-in-out infinite",
      },
      keyframes: {
        "pulse-soft": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.45" },
        },
      },
    },
  },
  plugins: [],
};
