import { redirect } from "next/navigation"

/** App entry — always land on login; session resume happens after auth. */
export default function Home() {
  redirect("/login")
}
