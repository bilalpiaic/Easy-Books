"use client"
import HubPage from "@/components/hub/HubPage"
import { INVENTORY_CONFIG } from "@/lib/hubConfigs"

export default function InventoryHub() {
  return <HubPage config={INVENTORY_CONFIG} />
}
