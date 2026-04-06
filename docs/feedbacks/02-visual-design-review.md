# OpenMarket Visual Design Review — Aesthetics Perspective

**Reviewer:** Customer who values beautiful, polished visual design
**Date:** 2026-04-03
**Design Score: 2.5 / 10**

---

## Overall Impression

This is a developer's first pass, and it reads exactly like one. The UI gets the job done functionally, but it has no visual identity, no design system, and no emotional presence. Compared to Shopify, Linear, or even a basic Tailwind starter kit, this feels like a browser-rendered wireframe from 2009. None of the three apps feel related to each other by design.

---

## What Works Well

- **POS layout has the right bones.** Two-column split (scan/search left, sale items right) is sensible. `height: 100vh` is correct for fullscreen POS.
- **"Complete Sale" button is the only styled button.** Green background, white text, full width, appropriate padding. It actually communicates importance.
- **CartCheckoutPage has the tightest layout focus.** `maxWidth: 600` with `margin: "0 auto"` is a conscious layout decision.
- **Expandable row pattern in Admin** — reasonable UX pattern for data tables.
- **Low-stock warning uses color differentiation** — red + bold. Blunt but functional.

---

## Visual Issues

### Critical

- **No design system whatsoever.** Every component uses one-off inline `style={{}}` props. No shared color palette, no spacing scale, no typography scale, no reusable tokens.

- **Buttons are unstyled browser defaults everywhere except "Complete Sale."** Every button — "Add", "Close", "-", "+", "Remove", "Apply" — renders as the browser's default gray 3D button. No hover states, no focus rings, no visual hierarchy.

- **Typography is entirely unstyled.** No font family specified anywhere except POS (`fontFamily: "sans-serif"`). Heading levels jump around with no consistent scale.

- **Navigation has zero visual design.** `padding: "1rem"` with a bottom border and bare `<Link>` elements. No active-state styling, no brand color, no logo treatment.

### Major

- **Color palette is three grays and browser-default blue.** `#ddd`, `#eee`, `#f5f5f5`, `#f9f9f9`, `#333`, `#666`, `#999`. No intentional primary or accent color. Only brand-adjacent color is `#4CAF50` on one button in one app.

- **Admin table is semantically broken.** Each `<tr>` contains a single `<td colSpan>` with a flex `<div>` inside. Column headers don't align with content.

- **ShopPage product card shows almost no information.** No price, no image placeholder, no stock indicator. Grid looks anemic.

- **No empty states designed.** Empty cart: `<p>Your cart is empty</p>`. No illustration, icon, or centered text with breathing room.

- **Error states use raw `color: "red"`.** No error icon, no background, no border. Visually harsh.

- **"Place Order" button** has padding but no background color — still renders as gray browser button.

- **Spacing is inconsistent.** Gaps alternate between `0.5rem`, `1rem`, and `2rem` with no system.

### Minor

- **"X" remove button in POS** is literally the letter "X" with no styling. Should be a styled icon.
- **Border radius inconsistently applied.** Some cards use `4px`, others have none.
- **`<h4>` tags used for section labels** that should be styled labels or caption text.
- **POS success message** appears inline with no toast or animation.
- **Tab active state** in OrdersPage uses `fontWeight: bold` only. Nearly invisible as selection indicator.
- **Discount code input** has no style prop — renders at browser default width.

---

## Specific Suggestions

### 1. Establish a design token file immediately

Create `tokens.ts` in `@openmarket/shared`:

```ts
export const colors = {
  brand: "#5B47E0",
  brandHover: "#4A38C9",
  surface: "#FFFFFF",
  surfaceMuted: "#F7F7F8",
  border: "#E5E5E7",
  borderStrong: "#C7C7CC",
  textPrimary: "#1A1A1A",
  textSecondary: "#6B6B6B",
  danger: "#D93025",
  dangerSurface: "#FEF2F2",
  success: "#1A7F37",
  successSurface: "#F0FFF4",
};

export const spacing = { xs: "4px", sm: "8px", md: "16px", lg: "24px", xl: "40px" };
export const radius = { sm: "6px", md: "10px", lg: "16px" };
export const font = { body: "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif" };
```

### 2. Fix buttons across all files (highest ROI change)

Replace every bare `<button>` with styled variants:
- Base: `padding: "6px 14px"`, `borderRadius: "6px"`, `border: "1px solid #C7C7CC"`, `background: "#F7F7F8"`
- Primary: brand background, white text, no border
- Danger: red text, red border

### 3. Fix admin tables

Abandon `<td colSpan>` trick. Use proper `<td>` cells matching `<th>` columns, or drop `<table>` for CSS grid.

### 4. Add base font family to all App.tsx files

```tsx
<div style={{ fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif" }}>
```

### 5. Fix active tab state in OrdersPage

Replace `fontWeight: bold` with background color + text color toggle matching brand palette.

### 6. Give nav bar proper identity

Add sticky positioning, consistent height (56px), proper padding, and background color.

### 7. Add hover state to ShopPage product cards

Add `box-shadow` on hover and `border-color` transition for interactive feedback.

---

**Bottom line:** A single `tokens.ts` file, a shared `Button` component, fixing the base font, and adding a brand color to the nav would immediately take this from a 2.5 to a 6. The structural foundation is there — the surface just needs to be treated like it matters.
