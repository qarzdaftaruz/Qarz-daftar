export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        // Telegram theme variables — main.jsx orqali doim yorug'ga majburlangan
        tg: {
          bg:        'var(--tg-theme-bg-color, #ffffff)',
          'bg-sec':  'var(--tg-theme-secondary-bg-color, #f3f4f6)',
          text:      'var(--tg-theme-text-color, #111827)',
          hint:      'var(--tg-theme-hint-color, #6b7280)',
          btn:       'var(--tg-theme-button-color, #2563eb)',
          'btn-txt': 'var(--tg-theme-button-text-color, #ffffff)',
          link:      'var(--tg-theme-link-color, #2563eb)',
        },
        // Tasdiqlangan brend palitrasi
        brand: {
          primary: '#2563EB',  // Asosiy ko'k — tugmalar, aktiv holatlar, havolalar
          trust:   '#16A34A',  // Ishonch yashil — to'lov, tasdiq, qarzdor hero
          warn:    '#D97706',  // Ogohlantiruvchi — muddati o'tgan, yangi so'rov
          neutral: '#6B7280',  // Neytral o'rta matn
          ink:     '#111827',  // Neytral to'q — asosiy matn
          surface: '#F3F4F6',  // Yumshoq fon
          danger:  '#EF4444',  // Xavf — o'chirish, rad etish, bloklash
        },
      },
      fontFamily: {
        sans:    ['Inter', 'system-ui', 'sans-serif'],
        display: ['Manrope', 'Inter', 'system-ui', 'sans-serif'],
      },
      keyframes: {
        slideUp:  { '0%': { opacity: '0', transform: 'translateY(22px)' }, '100%': { opacity: '1', transform: 'none' } },
        fadeIn:   { '0%': { opacity: '0' }, '100%': { opacity: '1' } },
        sheetUp:  { '0%': { transform: 'translateY(100%)' }, '100%': { transform: 'translateY(0)' } },
        scaleIn:  { '0%': { transform: 'scale(0.92)', opacity: '0' }, '100%': { transform: 'scale(1)', opacity: '1' } },
        rise:     { '0%': { opacity: '0', transform: 'translateY(14px)' }, '100%': { opacity: '1', transform: 'none' } },
        rowIn:    { '0%': { opacity: '0', transform: 'translateY(10px)' }, '100%': { opacity: '1', transform: 'none' } },
        moneyIn:  { '0%': { opacity: '0', transform: 'scale(0.85)' }, '60%': { opacity: '1', transform: 'scale(1.05)' }, '100%': { transform: 'scale(1)' } },
        stampIn:  { '0%': { opacity: '0', transform: 'scale(0.55) rotate(-16deg)' }, '60%': { opacity: '1', transform: 'scale(1.1) rotate(3deg)' }, '100%': { opacity: '1', transform: 'scale(1) rotate(0)' } },
        shimmer:  { '0%': { backgroundPosition: '-600px 0' }, '100%': { backgroundPosition: '600px 0' } },
        sheen:    { '0%': { transform: 'translateX(-120%)' }, '60%': { transform: 'translateX(220%)' }, '100%': { transform: 'translateX(220%)' } },
        floaty:   { '0%,100%': { transform: 'translateY(0)' }, '50%': { transform: 'translateY(-5px)' } },
      },
      animation: {
        'slide-up': 'slideUp 0.42s cubic-bezier(0.22,1,0.36,1) forwards',
        'fade-in':  'fadeIn 0.2s ease-out',
        'sheet-up': 'sheetUp 0.38s cubic-bezier(0.32,0.72,0,1)',
        'scale-in': 'scaleIn 0.24s cubic-bezier(0.22,1,0.36,1) forwards',
        'rise':     'rise 0.5s cubic-bezier(0.22,1,0.36,1) both',
        'row-in':   'rowIn 0.42s cubic-bezier(0.22,1,0.36,1) both',
        'money-in': 'moneyIn 0.45s cubic-bezier(0.22,1,0.36,1)',
        'stamp-in': 'stampIn 0.5s cubic-bezier(0.34,1.56,0.64,1) forwards',
        'sheen':    'sheen 2.6s ease-in-out 0.4s infinite',
        'floaty':   'floaty 3.5s ease-in-out infinite',
      },
    },
  },
  plugins: [],
}
