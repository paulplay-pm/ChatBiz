import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';
import { devIam } from './vite-plugin-dev-iam';

export default defineConfig({
  plugins: [react(), devIam()],
  resolve: {
    alias: { '@': path.resolve(__dirname, 'src') },
  },
  server: {
    port: 5173,
    proxy: {
      '/api/nodes': 'http://localhost:8001',
      '/workflows': 'http://localhost:8001',
      '/runs': 'http://localhost:8001',
      '/approvals': 'http://localhost:8001',
    },
  },
  build: { target: 'es2022', sourcemap: true, outDir: 'dist' },
});
