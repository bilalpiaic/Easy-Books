import type { Preview } from "@storybook/nextjs-vite"
import "../src/app/globals.css"

const preview: Preview = {
  parameters: {
    layout: "padded",
    controls: { matchers: { color: /(background|color)$/i, date: /Date$/i } },
    backgrounds: {
      options: {
        page: { name: "Page", value: "var(--bg-page)" },
        card: { name: "Card", value: "var(--bg-card)" },
      },
    },
  },
  initialGlobals: {
    backgrounds: { value: "page" },
  },
  decorators: [
    (Story) => (
      <div className="min-h-[40vh] font-sans text-[var(--text-primary)] antialiased">
        <Story />
      </div>
    ),
  ],
}

export default preview
