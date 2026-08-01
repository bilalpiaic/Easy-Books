import type { Meta, StoryObj } from "@storybook/nextjs-vite"
import { Package } from "lucide-react"
import { EmptyStateGuide } from "./EmptyStateGuide"

const meta = {
  title: "Guidance/EmptyStateGuide",
  component: EmptyStateGuide,
  tags: ["autodocs"],
  args: {
    title: "No bills of material yet",
    description:
      "A BOM lists the materials and quantities needed to make a finished good. Create one before releasing a production order.",
    steps: [
      "Create or pick the finished-good product.",
      "Add component lines with quantity per unit.",
      "Save — then use it on a production order.",
    ],
    primaryAction: { label: "Create BOM", href: "/manufacturing/boms/new" },
    secondaryAction: { label: "Open manufacturing guide", href: "/apps" },
  },
} satisfies Meta<typeof EmptyStateGuide>

export default meta
type Story = StoryObj<typeof meta>

export const WithSteps: Story = {}

export const Minimal: Story = {
  args: {
    title: "No invoices yet",
    description: "Create your first sales invoice to start tracking receivables.",
    steps: undefined,
    primaryAction: { label: "New invoice", href: "/invoices/new" },
    secondaryAction: undefined,
  },
}

export const CustomIcon: Story = {
  args: {
    title: "No products yet",
    icon: Package,
    primaryAction: { label: "Add product", href: "/products/new" },
  },
}
