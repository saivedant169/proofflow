import { defineConfig } from 'vite'

// Static product site. It has no backend dependency; the live app is linked, not proxied.
export default defineConfig({
  base: './',
  build: {
    target: 'es2022',
    sourcemap: false,
    chunkSizeWarningLimit: 700,
    rollupOptions: {
      onwarn(warning, warn) {
        // motion/lucide ship React Server Component directives that are meaningless in a static SPA.
        if (warning.code === 'MODULE_LEVEL_DIRECTIVE') return
        warn(warning)
      },
    },
  },
})
