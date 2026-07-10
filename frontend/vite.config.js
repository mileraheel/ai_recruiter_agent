import { writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// public/manifest.json is a static file, so Vite's built-in %ENV_VAR%
// substitution (which only applies to index.html) can't reach it.
// This plugin writes it from VITE_APP_NAME at the start of both `dev`
// and `build`, so the PWA name/short_name stay in sync with the same
// config that drives the page title and in-app header -- one place
// (.env's VITE_APP_NAME) to change instead of three.
function writeManifest(env) {
  return {
    name: "write-manifest",
    buildStart() {
      const appName = env.VITE_APP_NAME || "Role Pace";
      const manifest = {
        name: appName,
        short_name: appName,
        start_url: "/post-job",
        display: "standalone",
        background_color: "#faf9f6",
        theme_color: "#14141a",
        icons: [
          { src: "/icon-192.png", sizes: "192x192", type: "image/png" },
          { src: "/icon-512.png", sizes: "512x512", type: "image/png" },
        ],
      };
      writeFileSync(
        resolve(__dirname, "public/manifest.json"),
        JSON.stringify(manifest, null, 2) + "\n"
      );
    },
  };
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  return {
    plugins: [react(), writeManifest(env)],
    server: {
      host: true, // listen on 0.0.0.0 so devices on the same WiFi (e.g. your phone) can reach it
      port: 5173,
      // Vite rejects requests whose Host header isn't recognized (DNS-rebinding
      // protection), which otherwise blocks every request coming through the
      // public ngrok tunnel. This is the reserved domain rolepace.com's "Log in"
      // link points at -- see rolepace-site's index.html and this app's README
      // for the full tunnel setup. Update here if the reserved domain changes.
      allowedHosts: ["chlorine-patient-marshy.ngrok-free.dev"],
      proxy: {
        "/api": {
          target: "http://localhost:8000",
          changeOrigin: true,
        },
      },
    },
    test: {
      environment: "jsdom",
      globals: true,
      setupFiles: "./src/test/setup.js",
    },
  };
});
