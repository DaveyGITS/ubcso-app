const { defineConfig } = require('vite')
const { resolve } = require('path')

module.exports = defineConfig({
  build: {
    outDir: 'static',
    emptyOutDir: false,
    rollupOptions: {
      input: {
        main: resolve(__dirname, 'static/css/main.css'),
      },
      output: {
        assetFileNames: (assetInfo) => {
          if (assetInfo.name && assetInfo.name.endsWith('.css')) {
            return 'css/output.css'
          }
          return 'assets/[name][extname]'
        },
      },
    },
  },
})
