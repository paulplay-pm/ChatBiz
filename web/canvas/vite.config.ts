import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';
import { devIam } from './vite-plugin-dev-iam';

export default defineConfig(() => {
  const workflowEngineTarget = process.env.VITE_API_BASE || 'http://localhost:8001';
  const appBase = process.env.VITE_APP_BASE || '/';
  return {
    base: appBase,
    plugins: [react(), devIam()],
    resolve: {
      alias: { '@': path.resolve(__dirname, 'src'), ui: path.resolve(__dirname, '../ui') },
      dedupe: ['react', 'react-dom', 'react-router-dom'],
    },
    optimizeDeps: {
      include: ['react', 'react-dom', 'react-router-dom'],
    },
    server: {
      port: 5173,
      proxy: {
        '/api/nodes': workflowEngineTarget,
        '/workflows': workflowEngineTarget,
        '/runs': workflowEngineTarget,
        '/approvals': workflowEngineTarget,
      },
    },
    build: { target: 'es2022', sourcemap: true, outDir: 'dist' },
  };
});
