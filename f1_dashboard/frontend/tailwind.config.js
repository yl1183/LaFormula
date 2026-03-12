export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Space Grotesk', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      colors: {
        lf: {
          black: '#0A0A0F',
          dark: '#101018',
          card: '#16161F',
          surface: '#1C1C28',
          border: '#2A2A3A',
          muted: '#3A3A4D',
          text: '#8888A0',
          red: '#E10600',
          'red-glow': '#FF1A1A',
          green: '#00E676',
          yellow: '#FFD600',
          blue: '#448AFF',
          purple: '#B388FF',
          orange: '#FF9100',
          cyan: '#00E5FF',
        }
      },
      backgroundImage: {
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
        'carbon': 'repeating-linear-gradient(45deg, transparent, transparent 2px, rgba(255,255,255,0.02) 2px, rgba(255,255,255,0.02) 4px)',
      },
      boxShadow: {
        'glow-red': '0 0 20px rgba(225, 6, 0, 0.15)',
        'glow-green': '0 0 20px rgba(0, 230, 118, 0.15)',
        'card': '0 1px 3px rgba(0,0,0,0.4), 0 1px 2px rgba(0,0,0,0.3)',
        'card-hover': '0 4px 20px rgba(0,0,0,0.5), 0 0 0 1px rgba(225,6,0,0.1)',
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'slide-up': 'slideUp 0.3s ease-out',
        'fade-in': 'fadeIn 0.4s ease-out',
        'glow': 'glow 2s ease-in-out infinite alternate',
      },
      keyframes: {
        slideUp: {
          '0%': { transform: 'translateY(10px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        glow: {
          '0%': { boxShadow: '0 0 5px rgba(225, 6, 0, 0.2)' },
          '100%': { boxShadow: '0 0 20px rgba(225, 6, 0, 0.4)' },
        },
      },
    }
  },
  plugins: [],
}
