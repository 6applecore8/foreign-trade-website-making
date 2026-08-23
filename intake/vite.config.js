import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

// Desktop-local build. No 0.0.0.0 binding anywhere: Vite listens on
// localhost by default, and intake/server.py binds 127.0.0.1 only.
export default defineConfig({
  plugins: [
    vue(),
    {
      name: "dist-ownership-index",
      generateBundle() {
        this.emitFile({
          type: "asset",
          fileName: "INDEX.md",
          source: "# Generated production bundle\n\nOwned by `npm run build`; do not hand-edit. `index.html` references Vite-hashed files under `assets/`. Python serves only the index and contained assets.\n"
        });
      }
    }
  ],
  base: "/",
  server: {
    host: "127.0.0.1",
    proxy: {
      "/api": "http://127.0.0.1:4180"
    }
  },
  build: {
    outDir: "dist",
    emptyOutDir: true
  },
  test: {
    environment: "jsdom",
    globals: true,
    include: ["tests/**/*.test.js"]
  }
});
