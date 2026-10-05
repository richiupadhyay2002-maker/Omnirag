/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#07080d",
          900: "#0d0f18",
          800: "#141726",
          700: "#1c2033",
          600: "#282e46",
        },
        aurora: {
          400: "#7c8cff",
          500: "#6a5bff",
          600: "#5a3df0",
        },
        coral: {
          400: "#ff8a7a",
          500: "#ff6b57",
        },
        mint: {
          400: "#5eead4",
          500: "#2dd4bf",
        },
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        display: ["Sora", "Inter", "ui-sans-serif", "sans-serif"],
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(124,140,255,0.15), 0 8px 30px -8px rgba(90,61,240,0.45)",
        soft: "0 4px 20px -4px rgba(0,0,0,0.15)",
      },
      backgroundImage: {
        "aurora-radial": "radial-gradient(120% 120% at 10% 0%, #241e4d 0%, #0d0f18 55%)",
        "aurora-line": "linear-gradient(90deg, #7c8cff 0%, #ff6b57 50%, #2dd4bf 100%)",
      },
      keyframes: {
        floatSlow: { "0%,100%": { transform: "translateY(0)" }, "50%": { transform: "translateY(-8px)" } },
        fadeUp: { "0%": { opacity: 0, transform: "translateY(8px)" }, "100%": { opacity: 1, transform: "translateY(0)" } },
        pulseDot: { "0%,100%": { opacity: 0.3 }, "50%": { opacity: 1 } },
      },
      animation: {
        floatSlow: "floatSlow 6s ease-in-out infinite",
        fadeUp: "fadeUp 0.35s ease-out",
        pulseDot: "pulseDot 1.2s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
