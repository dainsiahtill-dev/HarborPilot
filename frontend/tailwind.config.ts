import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Vibrant AI Palette
        bg: {
          DEFAULT: "#02040a", // Deep Void
          panel: "#0f111a", // Glass Black
          surface: "#1e293b", // Slate-800/Surface
          highlight: "#334155", // Slate-700/Highlight
          secondary: "#0f111a", // Same as panel for consistency
          tertiary: "#1e293b",
        },
        border: {
          DEFAULT: "rgba(255, 255, 255, 0.1)",
          glow: "rgba(124, 58, 237, 0.4)", // Violet glow
        },
        accent: {
          DEFAULT: "#7c3aed", // Electric Violet (Primary)
          hover: "#8b5cf6", // Violet-500
          secondary: "#06b6d4", // Cyan (Secondary info)
          pink: "#db2777", // Hot Pink (Gradient end)
          dim: "rgba(124, 58, 237, 0.1)",
          text: "#c4b5fd", // Violet-200
        },
        status: {
          success: "#10b981", // Emerald-500
          warning: "#f59e0b", // Amber-500
          error: "#ef4444", // Red-500
          info: "#06b6d4", // Cyan-500
          secondary: "#ec4899", // Pink-500
        },
        text: {
          main: "#f8fafc", // Slate-50
          muted: "#94a3b8", // Slate-400
          dim: "#64748b", // Slate-500
        }
      },
      fontFamily: {
        sans: ['"Work Sans"', "ui-sans-serif", "system-ui", "sans-serif"],
        heading: ['"Outfit"', "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ['"Fira Code"', "ui-monospace", "monospace"],
      },
      backgroundImage: {
        'gradient-primary': 'linear-gradient(135deg, #7c3aed 0%, #db2777 100%)',
        'gradient-surface': 'linear-gradient(to bottom right, rgba(255,255,255,0.05), rgba(255,255,255,0.01))',
      },
      animation: {
        "pulse-slow": "pulse 4s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "fade-in": "fadeIn 0.4s ease-out",
        "slide-in": "slideIn 0.3s ease-out",
        "glow": "glow 2s ease-in-out infinite alternate",
      },
      keyframes: {
        fadeIn: {
          "0%": { opacity: "0", transform: "translateY(4px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        slideIn: {
          "0%": { transform: "translateY(10px)", opacity: "0" },
          "100%": { transform: "translateY(0)", opacity: "1" },
        },
        glow: {
          "0%": { boxShadow: "0 0 5px rgba(124, 58, 237, 0.2)" },
          "100%": { boxShadow: "0 0 20px rgba(124, 58, 237, 0.6), 0 0 10px rgba(219, 39, 119, 0.4)" },
        }
      },
      boxShadow: {
        "glow": "0 0 20px rgba(124, 58, 237, 0.3)",
        "glow-lg": "0 0 40px rgba(124, 58, 237, 0.4), 0 0 20px rgba(219, 39, 119, 0.3)",
        "panel": "0 8px 32px 0 rgba(0, 0, 0, 0.37)",
      }
    },
  },
  plugins: [],
} satisfies Config;
