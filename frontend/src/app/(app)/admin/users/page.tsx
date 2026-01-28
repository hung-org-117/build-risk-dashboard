'use client'

import { useState, useEffect, useCallback } from 'react'
import { Trash2, Shield, User, RefreshCw, Mail, Search, AlertCircle } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { toast } from '@/components/ui/use-toast'
import { DataTable, type DataTableColumn } from '@/components/ui/data-table'
import { adminUsersApi, usersApi } from '@/lib/api'
import { formatDateTime } from '@/lib/utils'
import type { UserAccount } from '@/types'

export default function AdminUsersPage() {
    const [users, setUsers] = useState<UserAccount[]>([])
    const [totalUsers, setTotalUsers] = useState(0)
    const [currentUserId, setCurrentUserId] = useState<string | null>(null)
    const [isLoading, setIsLoading] = useState(true)
    const [searchQuery, setSearchQuery] = useState('')

    // Pagination
    const [page, setPage] = useState(1)
    const pageSize = 20

    // Ban dialog state
    const [banUserId, setBanUserId] = useState<string | null>(null)
    const [banUserData, setBanUserData] = useState<UserAccount | null>(null)
    const [isBanning, setIsBanning] = useState(false)

    // Admin ban warning state
    const [showAdminWarning, setShowAdminWarning] = useState(false)

    const fetchCurrentUser = useCallback(async () => {
        try {
            const currentUser = await usersApi.getCurrentUser()
            setCurrentUserId(currentUser.id)
        } catch (err) {
            console.error('Failed to get current user:', err)
        }
    }, [])

    const fetchUsers = useCallback(async () => {
        setIsLoading(true)
        try {
            const response = await adminUsersApi.list(searchQuery || undefined, page, pageSize)
            setUsers(response.items)
            setTotalUsers(response.total)
        } catch (err) {
            console.error('Failed to load users:', err)
            toast({
                title: 'Error',
                description: 'Failed to load users',
                variant: 'destructive',
            })
        } finally {
            setIsLoading(false)
        }
    }, [searchQuery, page])

    useEffect(() => {
        fetchCurrentUser()
    }, [fetchCurrentUser])

    useEffect(() => {
        setPage(1) // Reset to page 1 when search changes
    }, [searchQuery])

    useEffect(() => {
        fetchUsers()
    }, [fetchUsers])

    const handleBanUser = async () => {
        if (!banUserId || !banUserData) return

        // Check if trying to ban an admin
        if (banUserData.role === 'admin') {
            setShowAdminWarning(true)
            return
        }

        setIsBanning(true)
        try {
            await adminUsersApi.delete(banUserId)
            setBanUserId(null)
            setBanUserData(null)
            fetchUsers()
            toast({ title: 'Success', description: 'User banned successfully' })
        } catch (err: any) {
            console.error('Failed to ban user:', err)
            const errorMessage = err?.response?.status === 403
                ? 'Cannot ban admin users'
                : 'Failed to ban user'
            toast({
                title: 'Error',
                description: errorMessage,
                variant: 'destructive',
            })
        } finally {
            setIsBanning(false)
        }
    }

    const handleUnbanUser = async (userId: string) => {
        try {
            await adminUsersApi.unban(userId)
            fetchUsers()
            toast({ title: 'Success', description: 'User unbanned successfully' })
        } catch (err) {
            console.error('Failed to unban user:', err)
            toast({
                title: 'Error',
                description: 'Failed to unban user',
                variant: 'destructive',
            })
        }
    }

    const columns: DataTableColumn<UserAccount>[] = [
        {
            key: 'user',
            header: 'User',
            render: (user) => {
                const initials = user.name
                    ? user.name.split(' ').filter(Boolean).map((p) => p[0]?.toUpperCase()).slice(0, 2).join('')
                    : user.email?.[0]?.toUpperCase() || '?'

                return (
                    <div className="flex items-center gap-2">
                        <div className="relative flex h-8 w-8 items-center justify-center overflow-hidden rounded-full bg-slate-200 text-xs font-semibold uppercase text-slate-600 dark:bg-slate-800 dark:text-slate-200">
                            {user.github?.avatar_url ? (
                                <img
                                    src={user.github.avatar_url}
                                    alt={user.name || user.email}
                                    className="h-full w-full object-cover"
                                />
                            ) : (
                                <span>{initials}</span>
                            )}
                        </div>
                        <span>{user.name || user.github?.login || '-'}</span>
                        {user.id === currentUserId && (
                            <Badge variant="outline" className="text-xs">You</Badge>
                        )}
                    </div>
                )
            },
        },
        {
            key: 'email',
            header: 'Email',
            render: (user) => (
                <div className="flex items-center gap-1 text-muted-foreground">
                    <Mail className="h-3 w-3" />
                    <span className="text-sm">{user.email}</span>
                </div>
            ),
        },
        {
            key: 'role',
            header: 'Role',
            render: (user) => (
                <Badge variant={user.role === 'admin' ? 'default' : 'secondary'}>
                    {user.role === 'admin' ? (
                        <Shield className="h-3 w-3 mr-1" />
                    ) : (
                        <User className="h-3 w-3 mr-1" />
                    )}
                    {user.role}
                </Badge>
            ),
        },
        {
            key: 'status',
            header: 'Status',
            render: (user) => (
                <div className="flex items-center gap-2">
                    {user.is_banned ? (
                        <Badge variant="destructive" className="bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400">
                            Banned
                        </Badge>
                    ) : (
                        <Badge variant="outline" className="bg-green-50 text-green-700 dark:bg-green-900/30 dark:text-green-400">
                            Active
                        </Badge>
                    )}
                </div>
            ),
        },
        {
            key: 'created_at',
            header: 'Created',
            render: (user) => (
                <span className="text-muted-foreground text-sm">
                    {formatDateTime(user.created_at)}
                </span>
            ),
        },
    ]

    return (
        <div className="flex flex-col gap-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <div>
                        <h1 className="text-2xl font-bold">User Management</h1>
                        <p className="text-sm text-muted-foreground">
                            Manage user accounts
                        </p>
                    </div>
                </div>
                <div className="flex gap-2">
                    <Button variant="outline" size="sm" onClick={fetchUsers} disabled={isLoading}>
                        <RefreshCw className={`h-4 w-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
                        Refresh
                    </Button>
                </div>
            </div>
            <Card>
                <CardHeader>
                    <div className="flex items-center justify-between">
                        <div>
                            <CardTitle>Users</CardTitle>
                            <CardDescription>
                                All registered users in the system
                            </CardDescription>
                        </div>
                        <div className="relative w-64">
                            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                            <Input
                                placeholder="Search users..."
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                                className="pl-8"
                            />
                        </div>
                    </div>
                </CardHeader>
                <CardContent className="p-0">
                    <DataTable
                        columns={columns}
                        data={users}
                        total={totalUsers}
                        page={page}
                        pageSize={pageSize}
                        loading={isLoading}
                        onPageChange={setPage}
                        rowKey={(user) => user.id}
                        emptyMessage={searchQuery ? 'No users found matching your search' : 'No users found'}
                        itemName="users"
                        actions={(user) => (
                            user.id !== currentUserId ? (
                                <div className="flex justify-end gap-1">
                                    {user.is_banned ? (
                                        // Unban button for banned users
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            className="text-blue-600 hover:text-blue-700 hover:bg-blue-50 dark:hover:bg-blue-900/20"
                                            onClick={() => handleUnbanUser(user.id)}
                                            title="Restore user access"
                                        >
                                            <RefreshCw className="h-4 w-4" />
                                        </Button>
                                    ) : (
                                        // Ban button for active users
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            className="text-destructive hover:text-destructive hover:bg-red-50 dark:hover:bg-red-900/20"
                                            onClick={() => {
                                                setBanUserData(user)
                                                setBanUserId(user.id)
                                                setShowAdminWarning(false)
                                            }}
                                            title="Ban user account"
                                        >
                                            <Trash2 className="h-4 w-4" />
                                        </Button>
                                    )}
                                </div>
                            ) : null
                        )}
                    />
                </CardContent>
            </Card>

            {/* Ban User Confirmation Dialog */}
            <Dialog open={!!banUserId && !showAdminWarning} onOpenChange={() => { setBanUserId(null); setBanUserData(null) }}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Ban User</DialogTitle>
                        <DialogDescription>
                            This user will be banned and unable to log in. Their account and data will be preserved for audit purposes. You can unban them later if needed.
                        </DialogDescription>
                    </DialogHeader>
                    {banUserData && (
                        <div className="bg-muted/50 p-3 rounded-md text-sm">
                            <p><strong>User:</strong> {banUserData.name || banUserData.email}</p>
                            <p><strong>Email:</strong> {banUserData.email}</p>
                            <p><strong>Role:</strong> {banUserData.role}</p>
                        </div>
                    )}
                    <DialogFooter>
                        <Button variant="outline" onClick={() => { setBanUserId(null); setBanUserData(null) }}>
                            Cancel
                        </Button>
                        <Button
                            variant="destructive"
                            onClick={handleBanUser}
                            disabled={isBanning}
                        >
                            {isBanning ? 'Banning...' : 'Ban User'}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* Admin Ban Warning Dialog */}
            <Dialog open={showAdminWarning} onOpenChange={setShowAdminWarning}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle className="flex items-center gap-2">
                            <AlertCircle className="h-5 w-5 text-yellow-600" />
                            Cannot Ban Admin User
                        </DialogTitle>
                        <DialogDescription>
                            Only regular users can be banned. Admin users must be demoted to a regular user role first before banning.
                        </DialogDescription>
                    </DialogHeader>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => { setShowAdminWarning(false); setBanUserId(null); setBanUserData(null) }}>
                            OK
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

        </div>
    )
}
