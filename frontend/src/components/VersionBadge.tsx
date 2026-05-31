export default function VersionBadge() {
  const v = process.env.NEXT_PUBLIC_APP_VERSION ?? "dev"
  return <span className="text-[11px] text-[#1a1814]/40">Easy-Books v{v}</span>
}
