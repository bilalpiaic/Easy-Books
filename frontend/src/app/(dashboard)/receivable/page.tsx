"use client"
import HubPage from "@/components/hub/HubPage"
import { RECEIVABLE_CONFIG } from "@/lib/hubConfigs"

export default function ReceivableHub() {
  return <HubPage config={RECEIVABLE_CONFIG} />
}
