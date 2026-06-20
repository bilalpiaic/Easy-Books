"use client"
import HubPage from "@/components/hub/HubPage"
import { PAYABLE_CONFIG } from "@/lib/hubConfigs"

export default function PayableHub() {
  return <HubPage config={PAYABLE_CONFIG} />
}
