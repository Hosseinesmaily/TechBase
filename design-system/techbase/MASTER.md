# TechBase design system

## Visual direction

Use the supplied UI/UX Pro Max reference as the visual target: a deep midnight navy canvas, a restrained cobalt glow on the left, and a soft warm copper glow on the right. Use translucent navy surfaces with fine cool borders. Keep the blue CTA as the strongest saturated color. The orange glow is atmospheric and should not reduce text contrast.

## Tokens

| Role | Value | Use |
|---|---|---|
| Page base | `#080D1B` | Outer canvas |
| Navy | `#101A31` | Background gradient midpoint |
| Surface | `rgba(20, 29, 49, .88)` | Cards, header, forms |
| Raised surface | `#172238` | Secondary panels and hover |
| Border | `#29364F` | Card and control edges |
| Main text | `#F1F5FB` | Headings and primary content |
| Muted text | `#A5B0C6` | Explanatory copy |
| Blue CTA | `#2868EE` | Primary action |
| Blue glow | `rgba(35, 82, 184, .30)` | Background atmosphere |
| Copper glow | `rgba(123, 58, 27, .27)` | Background atmosphere |

## Typography

Use Iran Sharp (`IRANSharp`) for Persian and English when the licensed webfont files are present in `frontend/public/fonts/`. The webfont package was not found on this machine, so do not bundle third-party copies; the current CSS falls back to IRANSansWeb, Tahoma, then Arial. Keep tabular hardware values legible with `dir="ltr"` where needed.

## Components

- Cards and navigation use dark translucent surfaces, a subtle border, and a soft shadow. Keep backgrounds calm so the blue and copper ambient gradients remain visible around them.
- Primary buttons use saturated blue with white text and a visible focus ring. Hover states deepen or brighten the blue without turning pale.
- Inputs use raised navy surfaces, cool borders, clear placeholders, and a distinct keyboard focus ring.
- Success, warning, and error states use muted dark-tinted backgrounds with light status text; color is not the sole signal.
- Use small, restrained motion and honor `prefers-reduced-motion`.

## Layout and RTL

- Persian is the default (`lang="fa"`, `dir="rtl"`). Keep navigation and forms usable at 320px and wider without page-level horizontal scrolling.
- Use logical spacing and borders (`ps-*`, `me-*`, `border-s-*`) for RTL-safe layout.
- Keep long product names and technical identifiers wrapping safely; use `dir="ltr"` for SKUs, socket names, and numeric measurements.
- Internal navigation uses `NuxtLink`.

## Quality checks

- Confirm primary and muted text contrast against the dark surfaces.
- Verify focus, hover, disabled, loading, success, warning, and error states.
- Check 375px, 768px, 1024px, and 1440px layouts and respect reduced-motion settings.
