"use client"

/**
 * Previously forced base-only users onto /onboarding (business-package wall).
 * Capabilities are now chosen via System → Add-ons; this guard is a no-op passthrough.
 */
export function OnboardingGuard({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}
