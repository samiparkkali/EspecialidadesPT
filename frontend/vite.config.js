import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// base must match the GitHub Pages repo path (https://<user>.github.io/<repo>/)
// so built asset URLs resolve correctly when not served from the domain root.
export default defineConfig({
  plugins: [react()],
  base: process.env.GITHUB_PAGES ? '/EspecialidadesPT/' : '/',
})
