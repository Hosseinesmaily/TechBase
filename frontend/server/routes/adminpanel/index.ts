/**
 * The same redirect for the trailing-slash form (`/adminpanel/`).
 *
 * Keeping both paths means the address works whichever way it is typed, and
 * there is still exactly one place that knows where the admin login lives.
 */
export { default } from "../adminpanel"
