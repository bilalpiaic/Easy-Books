"use client"

import { useEffect, useState } from "react"
import { apiFetch } from "@/lib/api"

interface PrintHeaderProps {
  /** Title of the report — e.g. "Trial Balance" */
  title: string
  /** Optional subtitle — e.g. "As of 2026-05-21" or "Period: Jan 2026 — May 2026" */
  subtitle?: string
  /** Set to "landscape" to add a class that switches the page orientation. */
  orientation?: "portrait" | "landscape"
}

interface CompanyInfo {
  name: string
  initial: string
  tagline?: string
  logo_url?: string
  address_line1?: string
  address_line2?: string
  city?: string
  country?: string
  phone?: string
  website?: string
  currency?: string
}

/**
 * Branded report header for printed/PDF output.
 *
 * Renders only on print (hidden on screen via `hidden print:block`).
 * Pulls company name and tagline from /api/settings; falls back to defaults.
 *
 * Use at the top of every report page:
 *   <PrintHeader title="Trial Balance" subtitle="As of 2026-05-21" />
 *
 * Add the `print-landscape` className to a containing element (or
 * pass orientation="landscape") to switch to landscape A4.
 */
export default function PrintHeader({
  title, subtitle, orientation = "portrait",
}: PrintHeaderProps) {
  const [info, setInfo] = useState<CompanyInfo>({ name: "Easy-Books", initial: "E", tagline: "Easy-Books · Double-Entry Accounting" })

  useEffect(() => {
    apiFetch<Record<string, string>>("/api/settings")
      .then(d => {
        const name = d?.company_name || "Easy-Books"
        setInfo({
          name,
          initial: name.charAt(0).toUpperCase(),
          tagline: d?.business_tagline || "Easy-Books · Double-Entry Accounting",
          logo_url: d?.logo_url,
          address_line1: d?.address_line1,
          address_line2: d?.address_line2,
          city: d?.city,
          country: d?.country,
          phone: d?.phone,
          website: d?.website,
          currency: d?.currency,
        })
      })
      .catch(() => {})
  }, [])

  const printedAt = new Date().toLocaleString(undefined, {
    year: "numeric", month: "short", day: "numeric",
    hour: "2-digit", minute: "2-digit",
  })

  return (
    <div
      className={`print-header hidden print:block ${orientation === "landscape" ? "print-landscape" : ""}`}
      role="presentation"
    >
      {/* Repeating page header (CSS targets this via the .print-header class
          so it appears at the top of every printed page). */}
      <div className="print-brand-row">
        <div className="print-brand">
          {info.logo_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={info.logo_url} alt={info.name} className="print-logo-img" />
          ) : (
            <div className="print-logo">{info.initial}</div>
          )}
          <div className="print-org">
            <div className="print-org-name">{info.name}</div>
            <div className="print-org-sub">{info.tagline}</div>
          </div>
        </div>
        <div className="print-meta">
          {info.address_line1 && <div className="print-meta-line">{info.address_line1}</div>}
          {info.address_line2 && <div className="print-meta-line">{info.address_line2}</div>}
          {(info.city || info.country) && (
            <div className="print-meta-line">
              {[info.city, info.country].filter(Boolean).join(", ")}
            </div>
          )}
          {(info.phone || info.website) && (
            <div className="print-meta-line">
              {info.phone && <span>{info.phone}</span>}
              {info.phone && info.website && <span> · </span>}
              {info.website && <span>{info.website}</span>}
            </div>
          )}
        </div>
      </div>

      <div className="print-title-row">
        <h1 className="print-title">{title}</h1>
        {subtitle && <p className="print-subtitle">{subtitle}</p>}
      </div>

      <div className="print-stamp">Generated {printedAt}</div>
    </div>
  )
}
