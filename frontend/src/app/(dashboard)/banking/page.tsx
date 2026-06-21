"use client"
import HubPage from "@/components/hub/HubPage"
import { BANKING_CONFIG } from "@/lib/hubConfigs"
import { useTranslation } from "react-i18next"

export default function BankingHub() {
  return <HubPage config={BANKING_CONFIG} />
}
