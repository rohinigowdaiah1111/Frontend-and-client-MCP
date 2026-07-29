---
name: Review Pulse Console
colors:
  surface: '#faf8ff'
  surface-dim: '#d9d9e5'
  surface-bright: '#faf8ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f3f3fe'
  surface-container: '#ededf9'
  surface-container-high: '#e7e7f3'
  surface-container-highest: '#e1e2ed'
  on-surface: '#191b23'
  on-surface-variant: '#434655'
  inverse-surface: '#2e3039'
  inverse-on-surface: '#f0f0fb'
  outline: '#737686'
  outline-variant: '#c3c6d7'
  surface-tint: '#0053db'
  primary: '#004ac6'
  on-primary: '#ffffff'
  primary-container: '#2563eb'
  on-primary-container: '#eeefff'
  inverse-primary: '#b4c5ff'
  secondary: '#505f76'
  on-secondary: '#ffffff'
  secondary-container: '#d0e1fb'
  on-secondary-container: '#54647a'
  tertiary: '#943700'
  on-tertiary: '#ffffff'
  tertiary-container: '#bc4800'
  on-tertiary-container: '#ffede6'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#dbe1ff'
  primary-fixed-dim: '#b4c5ff'
  on-primary-fixed: '#00174b'
  on-primary-fixed-variant: '#003ea8'
  secondary-fixed: '#d3e4fe'
  secondary-fixed-dim: '#b7c8e1'
  on-secondary-fixed: '#0b1c30'
  on-secondary-fixed-variant: '#38485d'
  tertiary-fixed: '#ffdbcd'
  tertiary-fixed-dim: '#ffb596'
  on-tertiary-fixed: '#360f00'
  on-tertiary-fixed-variant: '#7d2d00'
  background: '#faf8ff'
  on-background: '#191b23'
  surface-variant: '#e1e2ed'
typography:
  display-sm:
    fontFamily: Inter
    fontSize: 30px
    fontWeight: '600'
    lineHeight: 38px
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.01em
  headline-sm:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  label-md:
    fontFamily: Geist
    fontSize: 13px
    fontWeight: '500'
    lineHeight: 18px
    letterSpacing: 0.01em
  label-sm:
    fontFamily: Geist
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
  mono-sm:
    fontFamily: Geist
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  container-max: 1440px
  gutter: 24px
  margin-mobile: 16px
  margin-desktop: 32px
  unit-xs: 4px
  unit-sm: 8px
  unit-md: 16px
  unit-lg: 24px
  unit-xl: 32px
---

## Brand & Style
The design system is engineered for high-density information environments where clarity and operational speed are paramount. It adopts a **Minimalist / Modern** aesthetic, heavily influenced by the "Linear" school of thought—prioritizing functional purity, hairline borders, and a monochromatic foundation punctuated by purposeful semantic colors.

The target audience consists of data analysts and system administrators who require a "scannable" interface to monitor health and performance. The emotional response is one of **calm control** and **systemic reliability**. There are no decorative elements; every line, shadow, and margin exists to facilitate data legibility.

## Colors
This design system utilizes a refined, functional palette. The primary action color is a clean **Indigo-Blue**, reserved strictly for critical interactive triggers like "Reconnect" or "Retry". 

- **Neutral Scale:** A 10-step gray scale is used to create hierarchy. Backgrounds use the lightest tints, while text transitions from Slate-900 (Primary) to Slate-500 (Secondary/Muted).
- **Semantic Logic:** Statuses are strictly enforced. Green represents "Operational," Amber indicates "Degraded/Latency," and Red signals "Blocked/Disconnected." 
- **Dark Mode:** When toggled, the background shifts to a deep Zinc-950, surfaces move to Zinc-900, and borders utilize a low-opacity white (10%) to maintain the "hairline" feel without excessive contrast.

## Typography
The system uses **Inter** for all standard UI elements to ensure maximum legibility across different monitor resolutions. **Geist** (or a similar technical sans) is introduced for labels and monospaced data points to provide a subtle "developer-tool" texture.

Text hierarchy is strictly flat. We avoid excessive font size variance, instead using font weight (Medium/Semi-bold) and color (Slate-500 vs Slate-900) to distinguish between headers and metadata. All "Label" roles should be treated with a slightly tighter tracking for a professional, compact look.

## Layout & Spacing
The layout follows a **Fixed-Fluid hybrid grid**. On desktop, the dashboard is contained within a 1440px max-width wrapper. The internal structure uses a 12-column grid with a 24px gutter. 

Spacing is based on an **8px base unit**. 
- **Dashboards:** Use `unit-xl` (32px) for section padding to give the data room to breathe.
- **Card Internals:** Use `unit-md` (16px) for consistent internal padding.
- **Mobile:** The layout collapses to a single column with 16px side margins. Horizontal scrolling is permitted for data tables to preserve cell integrity.

## Elevation & Depth
This design system rejects heavy shadows in favor of **Tonal Layers** and **Low-Contrast Outlines**. 

- **Level 0 (Background):** Pure white or very light gray (#F9FAFB).
- **Level 1 (Cards):** White surface with a 1px border (#E2E8F0). No shadow.
- **Level 2 (Popovers/Modals):** White surface with a 1px border and a very soft, diffused ambient shadow (0px 4px 12px rgba(0,0,0,0.05)).
- **Interactive States:** On hover, a card may transition its border color to a slightly darker gray or the primary indigo, but it should not "lift" off the page.

## Shapes
The shape language is "Soft Professional." We use a conservative corner radius to maintain a precise, engineered feel.

- **Standard Elements:** 4px (0.25rem) for buttons, input fields, and small UI elements.
- **Containers/Cards:** 8px (0.5rem) for larger dashboard modules.
- **Status Pills:** Fully rounded (pill-shaped) to distinguish them from interactive buttons.

## Components
Consistent implementation of these components ensures the "operational" feel of the console:

- **Pill Badges:** Used for status. Small text (Label-sm), uppercase or capitalize. Background should be a 10% opacity version of the semantic color with a 100% opacity text color.
- **Status Dots:** 8px circles placed next to text. Use CSS "ping" animations only for "Error" or "Critical" states to draw immediate attention.
- **Usage Gauges:** Horizontal bar charts within table cells or cards. Use a subtle gray track with a solid semantic color fill. No gradients.
- **Vertical Steppers:** Used for "Sync Logs" or "Process History." Use 1px vertical lines to connect nodes. Completed steps use Primary Blue; pending steps use Slate-300.
- **Buttons:** 
    - **Primary:** Solid Blue, white text. Reserved for "Reconnect."
    - **Secondary:** White background, Slate-200 border, Slate-900 text. Used for "View" or "Retry."
- **Input Fields:** Minimal 1px border. On focus, the border changes to Primary Blue with a 2px soft blue outer glow (halo).