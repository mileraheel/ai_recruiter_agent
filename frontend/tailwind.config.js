/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#10152A",
        ink2: "#1B2140",
        paper: "#EDEDE4",
        paper2: "#FFFFFF",
        accent: "#21C7B0",
        accentDark: "#14584E",
        accentSoft: "#D9F3EE",
        amber: "#F2A93B",
        warn: "#8A5A12",
        warnSoft: "#FBEACD",
        danger: "#a3352f",
        dangerSoft: "#f8e6e4",
        slate: "#5B6478",
      },
      fontFamily: {
        sans: ["Public Sans", "system-ui", "sans-serif"],
        display: ["Big Shoulders Display", "sans-serif"],
        mono: ["IBM Plex Mono", "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
};
