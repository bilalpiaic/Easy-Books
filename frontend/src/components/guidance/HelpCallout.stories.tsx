import type { Meta, StoryObj } from "@storybook/nextjs-vite"
import { HelpCallout } from "./HelpCallout"

const meta = {
  title: "Guidance/HelpCallout",
  component: HelpCallout,
  tags: ["autodocs"],
  args: {
    title: "How purchase demands work",
    children:
      "A demand is quantity-only. Collect vendor quotations, pick a winner on the comparative, then convert to a PO. Self-approval is blocked.",
    defaultOpen: true,
    tone: "tip",
  },
} satisfies Meta<typeof HelpCallout>

export default meta
type Story = StoryObj<typeof meta>

export const Tip: Story = {}

export const Warning: Story = {
  args: {
    title: "Locked accounting period",
    tone: "warning",
    children:
      "This date falls in a locked period. Posting will be rejected until an admin re-opens the period or you pick a later date.",
  },
}

export const Success: Story = {
  args: {
    title: "Demo data loaded",
    tone: "success",
    children:
      "Seven sample companies are ready. Sign in with any demo.*@easy-books.app account and password demo1234.",
  },
}

export const Collapsed: Story = {
  args: { defaultOpen: false },
}
