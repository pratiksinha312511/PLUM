/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        background: "var(--background)",
        foreground: "var(--foreground)",
        muted: "var(--muted)",
        "muted-foreground": "var(--muted-foreground)",
        accent: "var(--accent)",
        "accent-secondary": "var(--accent-secondary)",
        "accent-muted": "var(--accent-muted)",
        border: "var(--border)",
        "border-hover": "var(--border-hover)",
        card: "var(--card)",
        ring: "var(--ring)",
        success: "var(--success)",
        danger: "var(--danger)",
        warning: "var(--warning)",
      },
      fontFamily: {
        serif: ["var(--font-serif)", "Georgia", "serif"],
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      letterSpacing: {
        smallcaps: "0.15em",
      },
      maxWidth: {
        editorial: "64rem",
      },
      boxShadow: {
        sm: "0 1px 2px rgba(26,26,26,0.04)",
        md: "0 4px 12px rgba(26,26,26,0.06)",
        lg: "0 8px 24px rgba(26,26,26,0.08)",
        accent: "0 6px 18px rgba(184,134,11,0.18)",
      },
    },
  },
  plugins: [],
};
