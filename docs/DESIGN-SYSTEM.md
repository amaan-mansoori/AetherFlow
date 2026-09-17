# Design System

**Status:** Architecture / Specification Phase

## Visual language

Dark neutral base, high-contrast text, restrained accent colors for state semantics, subtle borders, consistent spacing, and excellent typography. Color communicates status but is never the sole signal.

## Components

Use accessible primitives for navigation, command/search, forms, tables, badges, dialogs, tabs, pagination, timeline, code/JSON viewer, toast, skeleton, empty state, and error state. shadcn/ui is allowed where it reduces custom accessibility work; Lucide is the icon set.

## Motion

Motion/Framer Motion is limited to meaningful transitions such as panel changes, status updates, and loading feedback. Respect reduced-motion preferences. No animation exists solely to make a screen appear complex.

## Tokens

Define tokens for background/surface/border/text/accent/status colors, spacing, radius, typography, and elevation in one frontend theme. Components must use tokens rather than one-off values.

