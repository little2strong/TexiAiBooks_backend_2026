import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  return {
    plugins: [react({ jsxImportSource: mode === 'development' && env.VITE_UI_DIAGNOSTICS === 'true' ? '@welldone-software/why-did-you-render' : 'react' })],
    server: {
      port: 5173,
      strictPort: true,
      proxy: { '/api': { target: env.API_PROXY_TARGET || 'http://127.0.0.1:8000', changeOrigin: false } },
      headers: { 'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer' },
    },
    preview: { port: 5173, strictPort: true,
      proxy: { '/api': { target: env.API_PROXY_TARGET || 'http://127.0.0.1:8000', changeOrigin: false } },
      headers: { 'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer' } },
    build: { sourcemap: false },
  };
});
