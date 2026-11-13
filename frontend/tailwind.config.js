/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#0b1020",
        panel: "#10182c",
        card: "#151e33",
        line: "#2c3854",
        muted: "#93a0b8",
        accent: "#7aa2ff",
        violet: "#b39cff",
      },
    },
  },
  plugins: [],
};
