"use client"
import HubPage from "@/components/hub/HubPage"
import { RECEIVABLE_CONFIG } from "@/lib/hubConfigs"
import { useTranslation } from "react-i18next"

export default function ReceivableHub() {
  return <HubPage config={RECEIVABLE_CONFIG} />
}
