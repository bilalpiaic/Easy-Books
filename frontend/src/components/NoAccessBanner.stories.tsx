import type { Meta, StoryObj } from "@storybook/nextjs-vite"
import { NoAccessBanner } from "./NoAccessBanner"

const meta = {
  title: "Guidance/NoAccessBanner",
  component: NoAccessBanner,
  tags: ["autodocs"],
  args: { resource: "purchase demands" },
} satisfies Meta<typeof NoAccessBanner>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {}
