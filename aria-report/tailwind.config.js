/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: ["class"],
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        aria: {
          bg: "#08090a",
          panel: "#0f1011",
          surface: "#191a1b",
          "surface-2": "#28282c",
          text1: "#f7f8f8",
          text2: "#d0d6e0",
          text3: "#8a8f98",
          text4: "#62666d",
          brand: "#5e6ad2",
          accent: "#7170ff",
          "accent-hover": "#828fff",
          success: "#10b981",
        },
      },
      borderRadius: {
        xs: "2px",
        sm: "4px",
        md: "6px",
        lg: "8px",
        xl: "12px",
        "2xl": "22px",
        pill: "9999px",
      },
      fontFamily: {
        sans: ['Inter', '-apple-system', 'system-ui', 'sans-serif'],
        mono: ['Berkeley Mono', 'ui-monospace', 'SF Mono', 'Menlo', 'monospace'],
      },
      letterSpacing: {
        "display-xl": "-1.584px",
        "display-lg": "-1.408px",
        "display": "-1.056px",
        "heading-1": "-0.704px",
        "heading-2": "-0.288px",
        "heading-3": "-0.24px",
        "body-lg": "-0.165px",
        "caption-lg": "-0.182px",
        "caption": "-0.13px",
        "small": "-0.165px",
        "tiny": "-0.15px",
      },
      boxShadow: {
        "elevation-subtle": "rgba(0, 0, 0, 0.03) 0px 1.2px 0px 0px",
        "elevation-surface": "rgba(255, 255, 255, 0.05) 0px 0px 0px 1px",
        "elevation-inset": "rgba(0, 0, 0, 0.2) 0px 0px 12px 0px inset",
        "elevation-ring": "rgba(0, 0, 0, 0.2) 0px 0px 0px 1px",
        "elevation-elevated": "rgba(0, 0, 0, 0.4) 0px 2px 4px",
        "elevation-dialog": "rgba(0, 0, 0, 0) 0px 8px 2px, rgba(0, 0, 0, 0.01) 0px 5px 2px, rgba(0, 0, 0, 0.04) 0px 3px 2px, rgba(0, 0, 0, 0.07) 0px 1px 1px, rgba(0, 0, 0, 0.08) 0px 0px 1px",
        "elevation-focus": "rgba(0, 0, 0, 0.1) 0px 4px 12px",
      },
      keyframes: {
        "accordion-down": { from: { height: "0" }, to: { height: "var(--radix-accordion-content-height)" } },
        "accordion-up": { from: { height: "var(--radix-accordion-content-height)" }, to: { height: "0" } },
        "pulse-dot": { "0%, 100%": { opacity: "1", transform: "scale(1)" }, "50%": { opacity: "0.5", transform: "scale(0.8)" } },
        "bar-breathe": { "0%, 100%": { opacity: "0.7" }, "50%": { opacity: "1" } },
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
        "pulse-dot": "pulse-dot 1.4s ease-in-out infinite",
        "bar-breathe": "bar-breathe 1.5s ease-in-out infinite",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};
