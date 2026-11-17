/**
 * `/adminpanel` → the real, server-protected admin login.
 *
 * The route is a redirect only: it grants nothing. Authentication and the staff
 * check happen on the Django/Wagtail side (the admin login redirects anonymous
 * users and refuses non-staff accounts), so hiding or renaming the link is never
 * what protects the panel.
 *
 * Configure the admin origin with `NUXT_ADMIN_BASE_URL` (public runtime config).
 * Set it to `same-origin` when a reverse proxy publishes the admin on the site's
 * own domain; the redirect then stays relative (`/admin/login/`).
 */
export default defineEventHandler((event) => {
  const config = useRuntimeConfig(event)
  const base = String(config.public.adminBaseUrl || "").replace(/\/+$/, "")

  // `next` sends the editor back to the panel index after signing in.
  return sendRedirect(event, `${base}/admin/login/?next=/admin/`, 302)
})
