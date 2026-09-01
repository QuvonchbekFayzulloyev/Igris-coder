import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@shared': path.resolve(__dirname, 'shared'),
      '@web': path.resolve(__dirname, 'web'),
      // 2nd_brain/frontend komponentlari Igris_Interface tashqarisida —
      // bare import'lar (react, zustand) ularning qarshisida node_modules
      // yo'qligi uchun bu yerga yo'naltiriladi.
      react: path.resolve(__dirname, 'node_modules/react'),
      'react/jsx-runtime': path.resolve(__dirname, 'node_modules/react/jsx-runtime'),
      'react/jsx-dev-runtime': path.resolve(__dirname, 'node_modules/react/jsx-dev-runtime'),
      // MUHIM: zustand UCHUN alias QO'SHILMAYDI (bu yerda oldin bor edi va
      // butun appni buzdardi). `zustand` ni FAQAT Igris_Interface ichidagi
      // `shared/store.ts` import qiladi (2nd_brain/frontend zustand'ni to'g'ri
      // import qilmaydi) — shuning uchun u node_modules dan normal resolves
      // bo'ladi (ESM export map orqali `create` to'g'ri keladi). Alias
      // qo'yilganda (ayniqsa papkaga) Vite pre-bundle CJS ni tanlab,
      // \"does not provide an export named 'create'\" xatosi bilan app qora
      // bo'lib qolardi. Faqat react/re'akt sub-importlar shu yerdan aliased.
    },
  },
  server: {
    port: 1420,
    strictPort: true,
    fs: {
      // 2nd_brain/frontend komponentlari Igris_Interface tashqarisida —
      // dev server ularni /@fs/ orqali ham xizmat qila olishi kerak.
      allow: ['..'],
    },
    watch: {
      // Tauri Rust build artefaktlari Windows'da EBUSY beradi — kuzatuvdan chiqaramiz
      ignored: ['**/src-tauri/target/**'],
    },
  },
  build: {
    outDir: 'dist-web',
    sourcemap: true,
  },
});
