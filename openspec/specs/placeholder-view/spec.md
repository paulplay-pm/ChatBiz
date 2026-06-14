# placeholder-view Specification

## Purpose
TBD - created by archiving change admin-web-bootstrap. Update Purpose after archive.
## Requirements
### Requirement: PlaceholderView shows "Coming soon" card

The `PlaceholderView` component MUST render a centered card with:
- Title: "🚧 <MenuItemName> 即将推出"
- Body: "由后续 change <ChangeName> 落地"
- Style: white background, rounded-xl border, p-12, max-w-md mx-auto, mt-24, text-center

The component MUST accept props `{ menuItemName: string, changeName: string }`.

#### Scenario: Default render
- **WHEN** user opens `/mcp-tools` (no real view yet)
- **THEN** PlaceholderView renders the card with "MCP 工具 即将推出" + "由后续 change mcp-server-management-ui 落地"

#### Scenario: Per-route customization
- **WHEN** router maps `/workflow` to PlaceholderView with `{ menuItemName: "工作流", changeName: "workflow-engine" }`
- **THEN** the card shows "工作流 即将推出" + "由后续 change workflow-engine 落地"

### Requirement: PlaceholderView is visually consistent

The card MUST use Tailwind classes matching `docs/prototype.html`:
- Background: `bg-white`
- Border: `rounded-xl border border-dashed border-ink-300`
- Padding: `p-12`
- Width: `max-w-md mx-auto`
- Margin top: `mt-24`
- Text align: `text-center`
- Title: `text-xl font-semibold text-ink-800 mb-2`
- Body: `text-sm text-ink-500`

#### Scenario: Visual matches prototype
- **WHEN** user views the placeholder card
- **THEN** it matches the dashed-border style of `docs/prototype.html:4104-4107` (the "从市场安装" placeholder)

### Requirement: PlaceholderView shows a small icon

The card MUST include a `+` (plus) icon (FontAwesome `fas fa-plus`) above the title, sized 2xl, in `text-ink-400`, matching `docs/prototype.html:4158-4160` (the "添加 MCP Server" placeholder).

#### Scenario: Plus icon visible
- **WHEN** user views the placeholder card
- **THEN** a `+` icon appears above the title in gray color

