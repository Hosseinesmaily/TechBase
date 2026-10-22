export default defineNuxtConfig({
  ssr: true,
  devtools: { enabled: false },
  compatibilityDate: "2025-01-01",

  modules: ["@nuxtjs/tailwindcss"],

  css: ["~/assets/css/main.css"],

  typescript: { strict: true },

  app: {
    head: {
      htmlAttrs: { lang: "fa", dir: "rtl" },
      title: "تک‌بیس | پایگاه دانش سخت‌افزار",
      meta: [
        { charset: "utf-8" },
        { name: "viewport", content: "width=device-width, initial-scale=1" },
        {
          name: "description",
          content: "پایگاه دانش و ویکی سخت‌افزار کامپیوتر — راهنمای خرید، بنچمارک و پیشنهاد سیستم",
        },
      ],
    },
  },

  runtimeConfig: {
    // Server-side base for direct SSR calls; browser always uses the /api proxy.
    // Read at runtime (not baked at build time) so one build can be pointed at a
    // different API host by setting the env var.
    apiInternalBase: process.env.API_INTERNAL_BASE || "http://backend:8000",
    public: {
      siteName: "تک‌بیس",
    },
  },

  // The same-origin /api/** → Django proxy lives in server/api/[...path].ts
  // (a Nitro catch-all route), so nested paths and query strings work and the
  // upstream host stays a runtime value.
})
