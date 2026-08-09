import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

/**
 * Build paytida aniq CSP qo'shadi.
 *
 * vercel.json dagi header statik — u yerda API domenini oldindan bilib
 * bo'lmaydi va `connect-src https:` deb keng qoldirilgan. Bu plugin
 * VITE_API_URL dan aniq origin olib, `<meta>` CSP qo'shadi. Brauzer
 * ikkala CSP ni ham qo'llaydi va TORROQ qoida g'olib chiqadi —
 * ya'ni so'rovlar faqat sizning backend'ingizga keta oladi.
 */
function cspPlugin(apiUrl) {
  let apiOrigin = ''
  try { if (apiUrl) apiOrigin = new URL(apiUrl).origin } catch { /* noto'g'ri URL — o'tkazib yuboramiz */ }

  const csp = [
    "default-src 'self'",
    "script-src 'self' https://telegram.org",
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
    "font-src 'self' https://fonts.gstatic.com data:",
    "img-src 'self' data: blob:",
    `connect-src 'self'${apiOrigin ? ' ' + apiOrigin : ''}`,
    "base-uri 'self'",
    "form-action 'self'",
    "object-src 'none'",
  ].join('; ')

  return {
    name: 'inject-csp',
    apply: 'build',
    transformIndexHtml(html) {
      return {
        html,
        tags: [{
          tag: 'meta',
          attrs: { 'http-equiv': 'Content-Security-Policy', content: csp },
          injectTo: 'head-prepend',
        }],
      }
    },
  }
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  // Lokal ishlab chiqishda backend manzili (proxy uchun)
  const devApiTarget = env.VITE_DEV_API_TARGET || 'http://localhost:8000'

  return {
    plugins: [react(), cspPlugin(env.VITE_API_URL)],

    build: {
      target: 'es2020',
      // Production'da manba xaritalari yuklanmaydi — kod tuzilishi oshkor bo'lmasin
      sourcemap: false,
      cssCodeSplit: true,
      chunkSizeWarningLimit: 700,
      rollupOptions: {
        output: {
          manualChunks: {
            // Recharts og'ir — alohida chunk, faqat grafik sahifalarda yuklanadi
            recharts: ['recharts'],
            // React yadrosi — barqaror, brauzerda uzoq cache'lanadi
            'react-vendor': ['react', 'react-dom', 'react-router-dom'],
            // Tarmoq qatlami
            'net-vendor': ['axios'],
          },
        },
      },
    },

    server: {
      port: 5174,
      host: true,
      // ngrok/tunnel domenlari uchun (Telegram Mini App'ni lokal sinash)
      allowedHosts: env.VITE_ALLOWED_HOSTS
        ? env.VITE_ALLOWED_HOSTS.split(',').map(s => s.trim())
        : true,
      proxy: {
        '/api': { target: devApiTarget, changeOrigin: true },
      },
    },

    preview: { port: 4174 },
  }
})
