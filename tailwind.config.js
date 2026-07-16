module.exports = {
  darkMode: "class",
  content: [
    "./app/presentation/templates/**/*.html",
    "./app/presentation/static/**/*.js",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "Roboto", "ui-sans-serif", "system-ui"],
      },
      colors: {
        vnpt: {
          50: "#edf9ff",
          100: "#d6f1ff",
          500: "#087ccf",
          600: "#075fb0",
          700: "#07559c",
          900: "#0c4a6e",
          950: "#082a58",
        },
      },
      boxShadow: {
        soft: "0 18px 70px rgba(8, 42, 88, .12)",
      },
    },
  },
};
