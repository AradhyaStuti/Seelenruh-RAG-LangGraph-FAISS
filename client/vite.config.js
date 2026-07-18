import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
      },
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          // React core — changes rarely, long-lived cache hit
          'vendor-react': ['react', 'react-dom'],
          // Routing (if used)
          'vendor-router': ['react-hook-form', '@hookform/resolvers', 'zod'],
          // Markdown rendering — large, infrequently updated
          'vendor-markdown': ['react-markdown'],
          // Radix UI primitives bundle — large group but stable
          'vendor-ui': [
            '@radix-ui/react-dialog',
            '@radix-ui/react-dropdown-menu',
            '@radix-ui/react-scroll-area',
            '@radix-ui/react-tabs',
            '@radix-ui/react-tooltip',
            '@radix-ui/react-alert-dialog',
            '@radix-ui/react-avatar',
            '@radix-ui/react-label',
            '@radix-ui/react-slot',
          ],
          // Utility libs
          'vendor-utils': ['clsx', 'class-variance-authority', 'tailwind-merge', 'lucide-react'],
        },
      },
    },
    // Warn when any chunk exceeds 400 kB (down from default 500 kB)
    chunkSizeWarningLimit: 400,
  },
});
