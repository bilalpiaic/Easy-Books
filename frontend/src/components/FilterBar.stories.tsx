import { useState } from "react"
import type { Meta, StoryObj } from "@storybook/nextjs-vite"
import FilterBar from "./FilterBar"

const meta = {
  title: "Forms/FilterBar",
  component: FilterBar,
  tags: ["autodocs"],
} satisfies Meta<typeof FilterBar>

export default meta
type Story = StoryObj<typeof meta>

function FilterBarDemo() {
  const [search, setSearch] = useState("")
  const [status, setStatus] = useState("")
  const [dateFrom, setDateFrom] = useState("")
  const [dateTo, setDateTo] = useState("")
  return (
    <FilterBar
      search={search}
      onSearch={setSearch}
      statuses={["draft", "approved", "posted", "cancelled"]}
      status={status}
      onStatus={setStatus}
      dateFrom={dateFrom}
      dateTo={dateTo}
      onDateFrom={setDateFrom}
      onDateTo={setDateTo}
      placeholder="Search demands…"
    />
  )
}

export const Interactive: Story = {
  args: {
    search: "",
    onSearch: () => {},
  },
  render: () => <FilterBarDemo />,
}

export const SearchOnly: Story = {
  args: {
    search: "ACM",
    onSearch: () => {},
    placeholder: "Search customers…",
  },
}
