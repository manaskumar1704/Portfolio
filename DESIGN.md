# Design System Document: High-End Developer Editorial

## 1. Overview & Creative North Star
**The Creative North Star: "The Architectural Monolith"**

This design system moves away from the "template-heavy" world of traditional portfolios. Instead, it draws inspiration from high-end architectural journals and precision engineering tools. We are not just building a website; we are crafting a digital gallery for code.

The core philosophy relies on **Intentional Asymmetry** and **Tonal Depth**. We break the traditional grid by using extreme typographic scale contrasts—pairing massive, technical headers with microscopic, precise labels. The feel should be one of "Soft Brutalism": high-strength typography meets fluid, motion-based surfaces.

## 2. Colors & Surface Philosophy
The palette is rooted in deep obsidian tones and electric accents. The goal is to create a UI that feels like it’s glowing from within a void.

*   **Primary (`#abc7ff` / `#4691ff`):** Used sparingly for interactive focal points and "signature" elements.
*   **Surface (`#131313`):** The canvas. It is not pure black, but a deep, textured charcoal that allows for depth.
*   **The "No-Line" Rule:** 
    *   **Prohibition:** 1px solid borders are strictly forbidden for sectioning or grouping. 
    *   **Execution:** Boundaries must be defined solely through background color shifts. A section might transition from `surface` to `surface-container-low` to indicate a shift in context. Use whitespace as a structural element, not a gap.
*   **Surface Hierarchy & Nesting:** 
    *   Treat the UI as physical layers of stacked material.
    *   **Base:** `surface` (#131313).
    *   **Secondary Content:** `surface-container` (#202020).
    *   **Interactive/Elevated Elements:** `surface-container-high` (#2a2a2a).
*   **The "Glass & Gradient" Rule:** 
    *   To prevent a "flat" feel, use Glassmorphism for floating navigation and overlays. Use `surface` at 70% opacity with a `20px` backdrop-blur.
    *   **Signature Textures:** Apply a subtle linear gradient from `primary` to `primary-container` on high-value CTAs to provide a "metallic" sheen that implies premium quality.

## 3. Typography: The Technical Serif
We use **Space Grotesk** for its architectural rigidity and **Inter** for its neutral, high-readability utilitarianism.

*   **Display (Space Grotesk):** Massive scales (`display-lg` at 3.5rem) should be used for hero statements. Tighten letter-spacing (-0.04em) to create a "locked-in" editorial look.
*   **Headlines (Space Grotesk):** The "Technical Authority." These define section starts. Use `headline-lg` (2rem) in all-caps for a brutalist, developer-centric aesthetic.
*   **Body (Inter):** Your workhorse. `body-lg` (1rem) provides the human element. Keep line heights generous (1.6) to ensure the "whitespace" philosophy extends into the text blocks.
*   **Labels (Space Grotesk):** The "Metadata." Use `label-md` for technical specs (e.g., "TS / REACT / GLSL"). These should be high-contrast (`on-surface-variant`) and often paired with monospace-adjacent styling.

## 4. Elevation & Depth
Depth is achieved through **Tonal Layering**, not structural shadows.

*   **The Layering Principle:** Instead of shadows, place a `surface-container-lowest` card on a `surface-container-low` section. This create a "carved out" or "sunken" feel that is much more sophisticated than a drop shadow.
*   **Ambient Shadows:** If an element must float (like a modal), use a shadow color tinted with the `primary` token at 4% opacity with a 60px blur. It should feel like a soft glow, not a shadow.
*   **The "Ghost Border" Fallback:** If a container requires a border for accessibility, use `outline-variant` at **15% opacity**. It should be barely visible—a "suggestion" of a boundary.
*   **Motion-Based Depth:** Use CSS `parallax` or `transform: translateZ` on containers. As the user scrolls, surface layers should move at slightly different speeds, mimicking the physical stacking of glass plates.

## 5. Components

### Buttons
*   **Primary:** Background `primary-container`, text `on-primary-container`. High-gloss finish. No border.
*   **Secondary:** Background `transparent`, "Ghost Border" (15% `outline-variant`).
*   **Interaction:** On hover, buttons should expand slightly (scale 1.02) with a `300ms` spring transition.

### Cards & Projects
*   **Constraint:** No dividers. Use `2rem` of padding and a shift to `surface-container` to define the card area.
*   **Typography:** The project title should use `headline-sm`, while the "Year" or "Role" uses `label-sm` in the top right corner.

### Input Fields
*   **Style:** Minimalist underlines. Use `outline-variant` as the base line. On focus, the line expands from the center using the `primary` color.
*   **Background:** `surface-container-lowest` to create a "well" for the text.

### Chips (Tech Stack)
*   **Style:** Rectangular, `radius-sm` (0.125rem). Background `surface-container-highest`. Text `on-surface-variant`. These should look like physical CPU components or labels.

### Navigation (The Floating Dock)
*   A centered, bottom-fixed dock using Glassmorphism. `surface` at 60% opacity, `backdrop-blur: 12px`, and a "Ghost Border."

## 6. Do's and Don'ts

### Do:
*   **Do** use asymmetrical layouts. Push a text block 10% to the right to create visual tension.
*   **Do** use motion as a functional cue. Elements should "fade and slide" into view as the user scrolls.
*   **Do** use high-contrast color pairings (e.g., `primary` text on a `surface-container-lowest` background).

### Don't:
*   **Don't** use 100% opaque borders. They clutter the clean lines.
*   **Don't** use standard "Material" shadows. They feel dated and "out-of-the-box."
*   **Don't** crowd the layout. If you think there is enough whitespace, double it.
*   **Don't** use rounded corners larger than `xl` (0.75rem). This system thrives on the "sharp and precise" feel of `sm` and `md` radii.