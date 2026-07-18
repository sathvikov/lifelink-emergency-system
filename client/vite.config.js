import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],

  server: {
    host: '0.0.0.0',     // ⭐ allow all network IPs
    port: 5000,
    strictPort: true,
    allowedHosts: true   // ⭐ allow ALL hosts (ngrok fix)
  }
})
