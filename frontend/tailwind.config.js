/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        paper: "#FFFFFF",
        "paper-subtle": "#F6F7F9",
        ink: "#0A0A0A",
        "ink-deep": "#1E2544",
        "wild-muted": "#8B8B8B",
        "wild-muted-light": "#B3B9CA",
        "wild-blue-gray": "#6B7385",
        neon: "#D8FF00",
        "neon-lime": "#DCFC04",
        straw: "#F6D36D",
        "wild-red": "#E0492A",
        line: "rgba(10, 10, 10, 0.12)",
        "line-2": "rgba(10, 10, 10, 0.06)",
        brand: {
          50: "#f0fdf4",
          100: "#dcfce7",
          500: "#22c55e",
          600: "#16a34a",
          700: "#15803d",
          800: "#166534",
          900: "#14532d",
        },
      },
      fontFamily: {
        sans: [
          "-apple-system",
          "BlinkMacSystemFont",
          '"Segoe UI"',
          "Roboto",
          '"Helvetica Neue"',
          "Arial",
          "sans-serif",
        ],
        mono: [
          '"SFMono-Regular"',
          "ui-monospace",
          "Menlo",
          "Consolas",
          "monospace",
        ],
      },
      spacing: {
        cell: "14px",
        "cell-2": "28px",
        "cell-3": "35px",
        "cell-7": "98px",
        "cell-9": "126px",
        "cell-12": "168px",
        gutter: "56px",
      },
      borderRadius: {
        none: "0px",
        sm: "2px",
        md: "6px",
        pill: "26px",
      },
      maxWidth: {
        wild: "1440px",
        content: "1176px",
      },
    },
  },
  plugins: [],
};
