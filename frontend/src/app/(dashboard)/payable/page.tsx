"use client"
import HubPage from "@/components/hub/HubPage"
import { PAYABLE_CONFIG } from "@/lib/hubConfigs"
import { useTranslation } from "react-i18next"

export default function PayableHub() {
  return <HubPage config={PAYABLE_CONFIG} />
}
