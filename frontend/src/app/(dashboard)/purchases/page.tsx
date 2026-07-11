"use client"

import HubPage from "@/components/hub/HubPage"
import { PURCHASES_CONFIG } from "@/lib/hubConfigs"

export default function PurchasesHubPage() {
  return <HubPage config={PURCHASES_CONFIG} />
}
