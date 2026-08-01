import { useState } from "react"
import type { Meta, StoryObj } from "@storybook/nextjs-vite"
import Pagination from "./Pagination"

const meta = {
  title: "Forms/Pagination",
  component: Pagination,
  tags: ["autodocs"],
} satisfies Meta<typeof Pagination>

export default meta
type Story = StoryObj<typeof meta>

function PaginationDemo({ total = 127 }: { total?: number }) {
  const [page, setPage] = useState(1)
  return <Pagination page={page} pageSize={50} total={total} onPage={setPage} />
}

export const MultiPage: Story = {
  render: () => <PaginationDemo />,
}

export const HiddenWhenSinglePage: Story = {
  args: {
    page: 1,
    pageSize: 50,
    total: 12,
    onPage: () => {},
  },
}
