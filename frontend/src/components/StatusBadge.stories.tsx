import type { Meta, StoryObj } from "@storybook/nextjs-vite"
import StatusBadge from "./StatusBadge"

const meta = {
  title: "Forms/StatusBadge",
  component: StatusBadge,
  tags: ["autodocs"],
} satisfies Meta<typeof StatusBadge>

export default meta
type Story = StoryObj<typeof meta>

export const Draft: Story = { args: { status: "draft" } }
export const Approved: Story = { args: { status: "approved" } }
export const Posted: Story = { args: { status: "posted" } }
export const Paid: Story = { args: { status: "paid" } }
export const Overdue: Story = { args: { status: "overdue" } }
export const Cancelled: Story = { args: { status: "cancelled" } }

export const Gallery: Story = {
  render: () => (
    <div className="flex flex-wrap gap-2">
      {[
        "draft",
        "pending",
        "approved",
        "posted",
        "paid",
        "partial",
        "overdue",
        "void",
        "cancelled",
        "processing",
      ].map((s) => (
        <StatusBadge key={s} status={s} />
      ))}
    </div>
  ),
}
