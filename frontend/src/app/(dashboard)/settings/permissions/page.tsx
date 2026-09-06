"use client"
import { useEffect, useState, useCallback } from "react"
import { Shield, ChevronDown, ChevronRight, Save, Users, ShieldCheck, Database } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { useTranslation } from "react-i18next"

interface ResourceInfo {
  key: string
  label: string
  category: string
}

interface PermissionSet {
  permissions: Record<string, string>
  my_data_only: boolean
  module_enabled: boolean
}

interface TeamMember {
  id: number
  email: string
  full_name: string | null
  role: string
  is_active: boolean
}

type AccessLevel = "none" | "view" | "edit" | "default"

const LEVEL_LABELS: Record<string, string> = {
  none: "No Access",
  view: "View",
  edit: "Edit",
  default: "Role Default",
}

const LEVEL_COLORS: Record<string, string> = {
  none: "text-red-600",
  view: "text-blue-600",
  edit: "text-green-700",
  default: "text-gray-500",
}

export default function PermissionsPage() {
  const { t } = useTranslation()

  const [resources, setResources] = useState<ResourceInfo[]>([])
  const [members, setMembers] = useState<TeamMember[]>([])
  const [selectedUserId, setSelectedUserId] = useState<number | null>(null)
  const [permSet, setPermSet] = useState<PermissionSet | null>(null)
  const [drafts, setDrafts] = useState<Record<string, AccessLevel>>({})
  const [expanded, setExpanded] = useState<Record<string, boolean>>({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [moduleEnabled, setModuleEnabled] = useState(false)
  const [studioFields, setStudioFields] = useState<{ entity: string; key: string; label: string }[]>([])

  useEffect(() => {
    Promise.all([
      apiFetch<ResourceInfo[]>("/api/permissions/resources"),
      apiFetch<{ items: TeamMember[] }>("/api/users"),
      apiFetch<Record<string, string>>("/api/settings"),
      apiFetch<{ entity: string; key: string; label: string }[]>("/api/studio/fields").catch(() => []),
    ]).then(([res, team, settings, fields]) => {
      setResources(res)
      setMembers(team.items ?? [])
      setModuleEnabled(settings["user_rights_enabled"] === "true")
      setStudioFields(fields || [])
      if ((team.items ?? []).length > 0) {
        setSelectedUserId((team.items ?? [])[0].id)
      }
    }).finally(() => setLoading(false))
  }, [])

  const loadPerms = useCallback((userId: number) => {
    apiFetch<PermissionSet>(`/api/permissions/users/${userId}`)
      .then(data => {
        setPermSet(data)
        setDrafts({})
      })
  }, [])

  useEffect(() => {
    if (selectedUserId) loadPerms(selectedUserId)
  }, [selectedUserId, loadPerms])

  const categories = [...new Set(resources.map(r => r.category))]

  const getEffective = (key: string): string => {
    if (drafts[key] && drafts[key] !== "default") return drafts[key]
    if (drafts[key] === "default") return permSet?.permissions[key] ?? "edit"
    return permSet?.permissions[key] ?? "edit"
  }

  const handleChange = (key: string, level: AccessLevel) => {
    setDrafts(prev => ({ ...prev, [key]: level }))
  }

  const handleMyDataOnly = async (enabled: boolean) => {
    if (!selectedUserId) return
    await apiFetch(`/api/permissions/users/${selectedUserId}/my-data-only?enabled=${enabled}`, { method: "PATCH" })
    setPermSet(prev => prev ? { ...prev, my_data_only: enabled } : prev)
  }

  const handleSave = async () => {
    if (!selectedUserId || Object.keys(drafts).length === 0) return
    setSaving(true)
    const updates = Object.entries(drafts).map(([resource_key, access_level]) => ({
      resource_key,
      access_level,
    }))
    await apiFetch(`/api/permissions/users/${selectedUserId}`, {
      method: "PUT",
      body: JSON.stringify(updates),
    })
    setSaving(false)
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
    loadPerms(selectedUserId)
  }

  const selectedMember = members.find(m => m.id === selectedUserId)
  const hasDrafts = Object.keys(drafts).length > 0

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-[var(--text-primary)]/40 text-sm">Loading permissions…</div>
      </div>
    )
  }

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-[var(--primary)]/10 rounded-lg">
            <ShieldCheck className="w-6 h-6 text-[var(--primary)]" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-[var(--text-primary)]">Permissions</h1>
            <p className="text-sm text-[var(--text-primary)]/60">Control per-user access to each module</p>
          </div>
        </div>
        {!moduleEnabled && (
          <div className="px-3 py-1.5 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-700">
            User Rights Module is disabled. Enable it in Settings to enforce permissions.
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* User selector */}
        <div className="bg-white rounded-xl border border-[var(--border)] p-4 shadow-sm">
          <div className="flex items-center gap-2 mb-4">
            <Users className="w-4 h-4 text-[var(--primary)]" />
            <span className="text-sm font-semibold text-[var(--text-primary)]">Team Members</span>
          </div>
          <div className="space-y-1">
            {members.map(m => (
              <button
                key={m.id}
                onClick={() => setSelectedUserId(m.id)}
                className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors ${
                  selectedUserId === m.id
                    ? "bg-[var(--primary)] text-white"
                    : "hover:bg-[var(--bg-page)] text-[var(--text-primary)]"
                }`}
              >
                <div className="font-medium truncate">{m.full_name || m.email}</div>
                <div className={`text-xs ${selectedUserId === m.id ? "text-white/70" : "text-[var(--text-primary)]/50"}`}>
                  {m.role}
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Permission matrix */}
        <div className="lg:col-span-3 space-y-4">
          {selectedMember && (
            <div className="bg-white rounded-xl border border-[var(--border)] p-4 shadow-sm">
              <div className="flex items-center justify-between">
                <div>
                  <div className="font-semibold text-[var(--text-primary)]">
                    {selectedMember.full_name || selectedMember.email}
                  </div>
                  <div className="text-xs text-[var(--text-primary)]/50">Role: {selectedMember.role}</div>
                </div>
                <div className="flex items-center gap-4">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <span className="text-sm text-[var(--text-primary)]/70">My Data Only</span>
                    <div className="relative">
                      <input
                        type="checkbox"
                        checked={permSet?.my_data_only ?? false}
                        onChange={e => handleMyDataOnly(e.target.checked)}
                        className="sr-only peer"
                      />
                      <div className="w-9 h-5 bg-gray-300 rounded-full peer peer-checked:bg-[var(--primary)] peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-0.5 after:left-0.5 after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all" />
                    </div>
                  </label>
                  <button
                    onClick={handleSave}
                    disabled={!hasDrafts || saving}
                    className="flex items-center gap-2 px-4 py-2 bg-[var(--primary)] text-white rounded-lg text-sm font-medium hover:bg-[var(--primary-dark)] disabled:opacity-40 transition-colors"
                  >
                    <Save className="w-4 h-4" />
                    {saved ? "Saved!" : saving ? "Saving…" : "Save"}
                  </button>
                </div>
              </div>
            </div>
          )}

          {categories.map(cat => {
            const catResources = resources.filter(r => r.category === cat)
            const isOpen = expanded[cat] !== false  // default open
            return (
              <div key={cat} className="bg-white rounded-xl border border-[var(--border)] shadow-sm overflow-hidden">
                <button
                  onClick={() => setExpanded(prev => ({ ...prev, [cat]: !isOpen }))}
                  className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-[var(--bg-page)] transition-colors"
                >
                  <div className="flex items-center gap-2">
                    <Database className="w-4 h-4 text-[var(--primary)]" />
                    <span className="font-semibold text-sm text-[var(--text-primary)]">{cat}</span>
                    <span className="text-xs text-[var(--text-primary)]/40">({catResources.length})</span>
                  </div>
                  {isOpen ? (
                    <ChevronDown className="w-4 h-4 text-[var(--text-primary)]/40" />
                  ) : (
                    <ChevronRight className="w-4 h-4 text-[var(--text-primary)]/40" />
                  )}
                </button>
                {isOpen && (
                  <div className="border-t border-[var(--border)]">
                    {catResources.map((res, i) => {
                      const current = drafts[res.key] ?? "default"
                      const effective = getEffective(res.key)
                      return (
                        <div
                          key={res.key}
                          className={`flex items-center justify-between px-4 py-2.5 ${
                            i < catResources.length - 1 ? "border-b border-[var(--border)]" : ""
                          }`}
                        >
                          <div>
                            <span className="text-sm text-[var(--text-primary)]">{res.label}</span>
                            <span className={`ml-2 text-xs font-medium ${LEVEL_COLORS[effective]}`}>
                              ({effective})
                            </span>
                          </div>
                          <select
                            value={current}
                            onChange={e => handleChange(res.key, e.target.value as AccessLevel)}
                            className="text-xs px-2 py-1 border border-[var(--border)] rounded-lg focus:outline-none focus:ring-1 focus:ring-[var(--primary)] bg-white text-[var(--text-primary)]"
                          >
                            <option value="default">Role Default</option>
                            <option value="edit">Edit</option>
                            <option value="view">View</option>
                            <option value="none">No Access</option>
                          </select>
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
            )
          })}

          {studioFields.length > 0 && (() => {
            const isOpen = expanded["Fields"] === true
            const parentOf: Record<string, string> = {
              invoice: "invoices", bill: "bills", customer: "customers",
              vendor: "vendors", product: "products",
            }
            return (
              <div className="bg-white rounded-xl border border-[var(--border)] shadow-sm overflow-hidden">
                <button
                  onClick={() => setExpanded(prev => ({ ...prev, Fields: !isOpen }))}
                  className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-[var(--bg-page)] transition-colors"
                >
                  <div className="flex items-center gap-2">
                    <Database className="w-4 h-4 text-[var(--primary)]" />
                    <span className="font-semibold text-sm text-[var(--text-primary)]">Fields</span>
                    <span className="text-xs text-[var(--text-primary)]/40">({studioFields.length})</span>
                  </div>
                  {isOpen ? (
                    <ChevronDown className="w-4 h-4 text-[var(--text-primary)]/40" />
                  ) : (
                    <ChevronRight className="w-4 h-4 text-[var(--text-primary)]/40" />
                  )}
                </button>
                {isOpen && (
                  <div className="border-t border-[var(--border)]">
                    {studioFields.map((f, i) => {
                      const resKey = `${parentOf[f.entity] || f.entity}.field.${f.key}`
                      const current = drafts[resKey] ?? "default"
                      const effective = getEffective(resKey)
                      return (
                        <div
                          key={resKey}
                          className={`flex items-center justify-between px-4 py-2.5 ${
                            i < studioFields.length - 1 ? "border-b border-[var(--border)]" : ""
                          }`}
                        >
                          <div>
                            <span className="text-sm text-[var(--text-primary)]">{f.label}</span>
                            <span className="ml-2 text-xs text-[var(--text-primary)]/40">{f.entity} · {f.key}</span>
                            <span className={`ml-2 text-xs font-medium ${LEVEL_COLORS[effective] || LEVEL_COLORS.default}`}>
                              ({effective})
                            </span>
                          </div>
                          <select
                            value={current}
                            onChange={e => handleChange(resKey, e.target.value as AccessLevel)}
                            className="text-xs px-2 py-1 border border-[var(--border)] rounded-lg focus:outline-none focus:ring-1 focus:ring-[var(--primary)] bg-white text-[var(--text-primary)]"
                          >
                            <option value="default">Inherit parent</option>
                            <option value="edit">Edit</option>
                            <option value="view">View</option>
                            <option value="none">No Access</option>
                          </select>
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
            )
          })()}
        </div>
      </div>
    </div>
  )
}
