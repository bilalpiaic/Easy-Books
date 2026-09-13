/** FBR Digital Invoicing (PRAL DI API v1.12) — UI catalogs. */

export const DI_SALE_TYPES = [
  "Goods at standard rate (default)",
  "Goods at Reduced Rate",
  "Exempt goods",
  "Goods at zero-rate",
  "3rd Schedule Goods",
  "Steel melting and re-rolling",
  "Ship breaking",
  "Cotton Ginners",
  "Telecommunication services",
  "Toll Manufacturing",
  "Petroleum Products",
  "Electricity Supply to Retailers",
  "Gas to CNG stations",
  "Mobile Phones",
  "Processing/ Conversion of Goods",
  "Goods (FED in ST Mode)",
  "Services (FED in ST Mode)",
  "Services",
  "Electric Vehicle",
  "Cement /Concrete Block",
  "Potassium Chlorate",
  "CNG Sales",
  "Goods as per SRO.297(|)/2023",
  "Non-Adjustable Supplies",
] as const

export const DI_ACTIVITIES = [
  "Manufacturer",
  "Importer",
  "Distributor",
  "Wholesaler",
  "Exporter",
  "Retailer",
  "Service Provider",
  "Other",
] as const

export const DI_SECTORS = [
  "All Other Sectors",
  "Steel",
  "FMCG",
  "Textile",
  "Telecom",
  "Petroleum",
  "Electricity Distribution",
  "Gas Distribution",
  "Services",
  "Automobile",
  "CNG Stations",
  "Pharmaceuticals",
  "Wholesale / Retails",
] as const

export const DI_PROVINCES = [
  "Punjab",
  "Sindh",
  "Khyber Pakhtunkhwa",
  "Balochistan",
  "Islamabad Capital Territory",
  "Azad Jammu and Kashmir",
  "Gilgit-Baltistan",
] as const

export const DI_UOM = [
  "Numbers, pieces, units",
  "KG",
  "MT",
  "Litre",
  "Meter",
  "Square Metre",
  "Dozen",
  "KWH",
] as const

export const DI_INVOICE_TYPES = ["Sale Invoice", "Debit Note"] as const

export function namesFromRef(data: unknown, keys: string[]): string[] {
  if (!Array.isArray(data)) return []
  const out: string[] = []
  for (const row of data) {
    if (typeof row === "string" && row.trim()) {
      out.push(row.trim())
      continue
    }
    if (!row || typeof row !== "object") continue
    const rec = row as Record<string, unknown>
    for (const key of keys) {
      const val = rec[key]
      if (typeof val === "string" && val.trim()) {
        out.push(val.trim())
        break
      }
    }
  }
  return out
}
