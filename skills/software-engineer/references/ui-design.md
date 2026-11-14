# UI design

Use when the change touches a screen, form, dashboard, or CLI. The goal is an interface that steers attention to the right place so users finish their task without hunting. Work iteratively: understand users, tasks, and context → design objects, actions, and states → prototype → check with real tasks → repeat.

## Contents
1. Layout and visual hierarchy
2. Density limits
3. Headers, spacing, grouping
4. Emphasis
5. Consistency across an app or suite
6. Scrolling, overlays, typography
7. Components: tables, buttons, filters
8. Interaction checklist
9. Validate the design
10. Palantir Workshop specifics

The numbers below are rules of thumb (several come from Palantir's Workshop design guidance). Treat them as starting points, and follow the project's design system where it says otherwise.

## 1. Layout and visual hierarchy

People scan in an **F shape**: across the top, then down the left edge. Put the most important thing top-left, and keep configuration (filters, settings) visibly separate from content. Mirror this for right-to-left locales.

| Pattern | Reads | Use for |
|---|---|---|
| Grid | left to right, row by row | cards, galleries, equal-weight items |
| Columns | top to bottom, navigation at the top of each panel | master–detail, side-by-side comparison |
| Rows + columns | filters anchored on the left, content flowing right, summary numbers across the top | dashboards |

## 2. Density limits

Two different failures: **overload** (too many choices) and **overcrowding** (too many things on screen).

- At most ~5 primary actions in top-level navigation.
- Limit actionable items (tasks, notifications, choices) per screen; push the rest behind a secondary menu or a later step.
- At most ~10 visible components per view, counting buttons, panels, and widgets.
- Keep roughly 30–40% of the screen as whitespace.

Prefer a clear component over a clever one.

## 3. Headers, spacing, grouping

- One **page header** states what the page is for; it is the largest text and everything else relates to it.
- **Section headers** (second largest) group the content; add a one-line description only where the section's purpose isn't obvious.
- Write headers short, for someone seeing the app for the first time.
- Use one spacing scale throughout (16 px between elements is a safe default) and compact padding unless the design system says otherwise.
- **Containers** separate distinct groups; **dividers** separate related items inside one group. Put padding between groups too — a divider alone doesn't read as a boundary.

## 4. Emphasis

- Elevation (a drop shadow) says "this is the main thing". Use it once per page: the primary content area or the dialog where the user acts.
- Recessed or inset styling and darker backgrounds mark secondary areas such as filters and collapsible panels; lighter backgrounds mark primary content.
- If everything is emphasized, nothing is.

## 5. Consistency across an app or suite

- A **landing page** centralizes navigation and gives an overview of the modules.
- A **primary header** persists everywhere: logo top-left, global settings top-right.
- **Standard placement and styling**: filters always on the same side (left), and the same styles for tabs, metric cards, headers, and buttons on every page. Reuse existing components before making new ones.

## 6. Scrolling, overlays, typography

**Scrolling**
- Avoid horizontal scrolling; fit table columns to the available width instead.
- Keep navigation bars and tabs in the pinned header so only content scrolls.
- Touch targets inside scrollable areas: at least 30 px; aim for 44 px on touch-first screens.

**Overlays (dialogs, drawers)**
- Good for short, secondary interactions: a confirmation, a small form, a questionnaire.
- Poor for analysis, where users need to see several layers of information at once.
- A dialog blocks the page behind it. If users need to read long text while typing, put the inputs beside that text or repeat it somewhere non-blocking.
- Support select-then-act: the user picks one or more items, then triggers an action on them.

**Typography**
- Prefer the design system's default or a system font. A font referenced only by name renders differently on every device that lacks it.
- If a custom font is required, ship it with the app (web font) and declare a fallback stack.

## 7. Components: tables, buttons, filters

**Tables and lists**
- Show the row count next to the table's header, so users know how much is there (and whether a filter worked).
- Each row shows enough to decide whether to select it. Put the rest in a collapsible side or detail panel, not an overlay that hides the table.
- Apply the scrolling rules above: no horizontal scroll, header stays put.

**Buttons** — color follows the outcome or risk the user expects, not decoration:

| Intent | Color | Use for | Examples |
|---|---|---|---|
| Neutral | gray | secondary actions | Back, Skip, Cancel |
| Primary | blue | the main call to action; moving forward | Create, Add new, Next, Continue |
| Success | green | completing something; a positive outcome | Submit, Save, Approve, Enable |
| Warning | amber | needs attention, moderate risk, not destructive | Archive, Suspend, Review required |
| Danger | red | destructive and hard to undo; critical alerts | Delete, Remove |

- One primary action per group, placed first; order the rest left to right by importance. Collapse minor actions into a menu.
- Color only the primary action. A group where every button has its own color has no hierarchy.
- Express rank through size, border, and color intensity as well as hue.
- Icons should say what will happen: a horizontal arrow for moving within the app, an angled arrow for opening a new tab or window, a plus for related actions, an ellipsis for a menu of more.
- Labels in plain, sentence-case language. Don't repeat what the surrounding header already says (in an "Equipment" section, "Add", not "Add equipment").
- Put buttons next to the thing they act on — in that table's or section's own header, not a shared toolbar far away.

**Search and filtering** — match the control to the user and the job:

| Control | Fits when |
|---|---|
| Vertical filter list | several filters applied at once; complex filtering; users need to see every option |
| Filter pills | little screen space, frequent changes, newer users |
| Search bar with query support (keywords, field filters, combined conditions) | experienced users who need precise queries |

## 8. Interaction checklist

**Put the user in control**
- [ ] Modes are few, visible, and easy to enter and leave
- [ ] Long or multi-step tasks can be cancelled, undone, or resumed without losing input
- [ ] Works by keyboard as well as pointer/touch
- [ ] Internals stay hidden: no stack traces, raw IDs, or jargon in the UI

**Reduce memory load**
- [ ] Users never have to carry information from one screen to another in their head
- [ ] Sensible defaults, with a way back to them
- [ ] Options are visible and recognizable rather than recalled; labels over icons alone
- [ ] Terms and metaphors match the user's world
- [ ] Progressive disclosure: summary first, detail on demand

**Be consistent**
- [ ] Reuses the app's existing components, wording, spacing, and platform conventions
- [ ] The same action looks and behaves the same everywhere

**Feedback and errors**
- [ ] Every action gets visible feedback; anything slow shows progress
- [ ] Errors are prevented where possible: constrained inputs, invalid actions disabled, destructive actions confirmed or undoable
- [ ] Error messages say what went wrong and how to fix it, next to the cause, and keep the user's input
- [ ] Empty, loading, and error states are designed, not left blank

**Accessibility**
- [ ] Semantic elements and labels on every control; images have alt text
- [ ] Logical focus order with a visible focus indicator
- [ ] Text contrast meets WCAG AA (4.5:1 for body text); color is never the only signal
- [ ] Layout survives text zoom and narrow screens

**CLI**: `--help` with examples, consistent flag names, errors to stderr, non-zero exit code on failure.

## 9. Validate the design

- [ ] **Squint test** — blur your eyes (or the screenshot): the elements that still stand out should be the ones that matter most
- [ ] Walked through the real user workflow for each section, not an imagined one
- [ ] Every visible element earns its place here; anything else appears only when the user needs to act on it
- [ ] Density limits in section 2 hold; one primary action per button group
- [ ] Looked at the rendered result (browser or screenshot), at narrow and wide widths

## 10. Palantir Workshop specifics

Only for Foundry Workshop modules.

| Goal | Where |
|---|---|
| Choose a layout | **Set layout** after adding a widget; for an existing section, select it and use **Layout** in the right panel |
| Header and description | Toggle **Section header** in the Section panel; fill Title and Description |
| Padding | **Compact** by default; a custom setting of 80% height or width with 16 px spacing works across layout types |
| Emphasis | Border styles with elevation; outer drop shadow on the main content or primary modal only |
| No horizontal scroll in tables | **Fit columns horizontally** in the Object Table's Display & Formatting settings |
| Key numbers at a glance | Metric Card widget |
| Row count on a table or list | Metric Card in the table's section header, layout style **Tag** |
| Extra detail for a selected row | Collapsible detail panel holding an object view, not an overlay |
| Table appearance; button size, border, color intensity | **Display & formatting** in the Widget setup panel |
| Button color | Button Group **Intent**: None, Primary, Success, Warning, Danger |
| Filters | Filtering widgets in the left-most section. Filter List **Vertical** layout for multi-filter work, **Pills** layout or Exploration Filter Pills for compact filtering, Exploration Search Bar for precise queries |
| Fonts | Settings → Module Appearance → Typography. Default is Source Sans Pro. A custom typeface renders only if it is installed on the viewer's device and fonts can't be uploaded, so pick a system font for consistent rendering |
