'use client'

import { useEffect, type ReactNode } from 'react'
import { Loader2 } from 'lucide-react'
import { useRouter } from 'next/navigation'

import { useAuth } from '@/contexts/auth-context'

interface RequireAdminProps {
    children: ReactNode
    fallbackPath?: string
}

/**
 * Component that requires admin role to view its children.
 * Redirects non-admin users to the fallback path (default: /overview).
 */
export function RequireAdmin({ children, fallbackPath = '/overview' }: RequireAdminProps) {
    const router = useRouter()
    const { authenticated, loading, user } = useAuth()

    const isAdmin = user?.role === 'admin'

    useEffect(() => {
        if (loading) return

        if (!authenticated) {
            router.replace('/login')
            return
        }

        if (!isAdmin) {
            router.replace(fallbackPath)
        }
    }, [authenticated, loading, isAdmin, router, fallbackPath])

    // Show loading while checking auth
    if (loading) {
        return (
            <div className="flex min-h-[400px] items-center justify-center">
                <div className="flex flex-col items-center gap-2 text-sm text-muted-foreground">
                    <Loader2 className="h-6 w-6 animate-spin text-blue-500" />
                    <span>Checking permissions…</span>
                </div>
            </div>
        )
    }

    // Show loading while redirecting non-admin
    if (!authenticated || !isAdmin) {
        return (
            <div className="flex min-h-[400px] items-center justify-center">
                <div className="flex flex-col items-center gap-2 text-sm text-muted-foreground">
                    <Loader2 className="h-6 w-6 animate-spin text-blue-500" />
                    <span>Redirecting…</span>
                </div>
            </div>
        )
    }

    return <>{children}</>
}
