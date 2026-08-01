import type { Meta, StoryObj } from "@storybook/nextjs-vite"
import { FieldHint } from "./FieldHint"

const meta = {
  title: "Guidance/FieldHint",
  component: FieldHint,
  tags: ["autodocs"],
  parameters: {
    docs: {
      description: {
        component:
          "Subtle inline hint under a form field — explain what the field does for accounting, not the placeholder.",
      },
    },
  },
} satisfies Meta<typeof FieldHint>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  args: {
    children:
      "NTN is used on PRA e-invoices and tax reports. Leave blank if the party is unregistered.",
  },
  render: (args) => (
    <label className="block max-w-md">
      <span className="text-sm font-medium">NTN / Tax ID</span>
      <input
        className="mt-1 w-full rounded-lg border border-[var(--border)] px-3 py-2 text-sm"
        placeholder="e.g. 1234567-8"
      />
      <FieldHint {...args} />
    </label>
  ),
}
