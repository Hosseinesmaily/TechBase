import type { Config } from "tailwindcss"

export default {
  content: [
    "./app.vue",
    "./components/**/*.{vue,js,ts}",
    "./layouts/**/*.vue",
    "./pages/**/*.vue",
    "./plugins/**/*.{js,ts}",
  ],
  theme: {
    extend: {
      colors: {
        surface: {
          DEFAULT: "#111a2d",
          soft: "#172238",
          raised: "#1b2842",
        },
        slate: {
          50: "#111a2d",
          100: "#172238",
          200: "#29364f",
          300: "#3a4965",
          400: "#8190ab",
          500: "#a5b0c6",
          600: "#bac4d8",
          700: "#d0d8e8",
          800: "#e3e9f4",
          900: "#f1f5fb",
          950: "#f8fafc",
        },
        brand: {
          50: "#111d38",
          100: "#17284a",
          200: "#203b68",
          300: "#31518b",
          400: "#4b83ff",
          500: "#3479ff",
          600: "#2868ee",
          700: "#91b5ff",
          800: "#bbd1ff",
          900: "#e0eaff",
        },
        emerald: {
          50: "#102b2a",
          100: "#153a37",
          200: "#1c514b",
          400: "#34d399",
          500: "#10b981",
          600: "#6ee7b7",
          700: "#a7f3d0",
        },
        amber: {
          50: "#30251b",
          100: "#3c2d1c",
          200: "#654524",
          400: "#fbbf24",
          500: "#f59e0b",
          600: "#fcd34d",
          700: "#fde68a",
        },
        rose: {
          50: "#321e2b",
          100: "#422231",
          200: "#672b3d",
          400: "#fb7185",
          500: "#f43f5e",
          600: "#fda4af",
          700: "#fecdd3",
        },
      },
    },
  },
} satisfies Config
