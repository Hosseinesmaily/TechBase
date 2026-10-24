import type { RouterConfig } from "@nuxt/schema"

export default <RouterConfig>{
  scrollBehavior(to) {
    if (to.hash) {
      return { el: to.hash, behavior: "smooth" }
    }

    // Always begin a route at the top, including browser back/forward navigation.
    return { left: 0, top: 0 }
  },
}
