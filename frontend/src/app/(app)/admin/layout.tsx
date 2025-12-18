'use client'

import { type ReactNode, useEffect } from 'react'
import { usePathname, useRouter } from 'next/navigation'
import { Loader2 } from 'lucide-react'

import { useAuth } from '@/contexts/auth-context'

// Routes that only admin can access
const ADMIN_ONLY_ROUTES = ['/admin/monitoring', '/admin/users', '/admin/settings']

// Routes that admin AND guest can access (viewer routes)
const VIEWER_ROUTES = ['/admin/datasets', '/admin/repos']

export default function AdminLayout({ children }: { children: ReactNode }) {
    const router = useRouter()
    const pathname = usePathname()
    const { authenticated, loading, user } = useAuth()

    const role = user?.role
    const isAdmin = role === 'admin'
    const isGuest = role === 'guest'
    const isViewer = isAdmin || isGuest

    // Determine required access level for current route
    const isAdminOnlyRoute = ADMIN_ONLY_ROUTES.some(route => pathname.startsWith(route))
    const isViewerRoute = VIEWER_ROUTES.some(route => pathname.startsWith(route))

    // Check access
    const hasAccess = isAdminOnlyRoute ? isAdmin : (isViewerRoute ? isViewer : isAdmin)

    useEffect(() => {
        if (loading) return

        if (!authenticated) {
            router.replace('/login')
            return
        }

        if (!hasAccess) {
            // Redirect non-authorized users
            if (isGuest && isAdminOnlyRoute) {
                // Guest trying to access admin-only route
                router.replace('/admin/datasets')
            } else {
                // Regular user trying to access admin area
                router.replace('/overview')
            }
        }
    }, [authenticated, loading, hasAccess, isGuest, isAdminOnlyRoute, router])

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

    // Show loading while redirecting
    if (!authenticated || !hasAccess) {
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
