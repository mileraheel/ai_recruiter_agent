/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#14141a",
        paper: "#faf9f6",
        accent: "#2f6f4f",
        accentSoft: "#e8f2ec",
        warn: "#b5651d",
        warnSoft: "#fbe9dc",
        danger: "#a3352f",
        dangerSoft: "#f8e6e4",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
