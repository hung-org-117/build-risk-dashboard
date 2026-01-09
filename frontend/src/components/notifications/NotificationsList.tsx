'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { CheckCheck, ExternalLink, Bell, Loader2, Filter } from 'lucide-react'
import { useRouter } from 'next/navigation'
import { formatDistanceToNow } from 'date-fns'

import { notificationsApi } from '@/lib/api'
import type { Notification } from '@/types'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'



type FilterStatus = 'all' | 'unread' | 'read'

const ITEMS_PER_PAGE = 10
const SCROLL_THRESHOLD_PX = 140

export function NotificationsList() {
    const router = useRouter()
    const scrollContainerRef = useRef<HTMLDivElement>(null)
    const [notifications, setNotifications] = useState<Notification[]>([])
    const [isLoading, setIsLoading] = useState(true)
    const [isLoadingMore, setIsLoadingMore] = useState(false)
    const [isMarkingAll, setIsMarkingAll] = useState(false)
    const [nextCursor, setNextCursor] = useState<string | null>(null)
    const [hasMore, setHasMore] = useState(false)
    const [filter, setFilter] = useState<FilterStatus>('all')

    // Initial load
    const loadNotifications = useCallback(async () => {
        try {
            setIsLoading(true)
            const notificationListResponse = await notificationsApi.list({
                limit: ITEMS_PER_PAGE
            })
            setNotifications(notificationListResponse.items)
            setNextCursor(notificationListResponse.next_cursor || null)
            setHasMore(!!notificationListResponse.next_cursor)
        } catch (error) {
            console.error('Failed to fetch notifications:', error)
        } finally {
            setIsLoading(false)
        }
    }, [])

    useEffect(() => {
        loadNotifications()
    }, [loadNotifications])

    const loadMoreNotifications = useCallback(async () => {
        if (!nextCursor || isLoadingMore) {
            return
        }

        try {
            setIsLoadingMore(true)
            const notificationListResponse = await notificationsApi.list({
                limit: ITEMS_PER_PAGE,
                cursor: nextCursor
            })

            setNotifications((currentNotifications) => [
                ...currentNotifications,
                ...notificationListResponse.items
            ])
            setNextCursor(notificationListResponse.next_cursor || null)
            setHasMore(!!notificationListResponse.next_cursor)
        } catch (error) {
            console.error('Failed to load more notifications:', error)
        } finally {
            setIsLoadingMore(false)
        }
    }, [isLoadingMore, nextCursor])

    const handleScroll = useCallback(() => {
        const scrollContainer = scrollContainerRef.current
        if (!scrollContainer || isLoadingMore || !hasMore) {
            return
        }

        const remainingScroll =
            scrollContainer.scrollHeight - scrollContainer.scrollTop - scrollContainer.clientHeight

        if (remainingScroll <= SCROLL_THRESHOLD_PX) {
            void loadMoreNotifications()
        }
    }, [hasMore, isLoadingMore, loadMoreNotifications])

    useEffect(() => {
        const scrollContainer = scrollContainerRef.current
        if (!scrollContainer || isLoading || isLoadingMore || !hasMore) {
            return
        }

        const scrollFillGap = scrollContainer.scrollHeight - scrollContainer.clientHeight
        if (scrollFillGap <= SCROLL_THRESHOLD_PX) {
            void loadMoreNotifications()
        }
    }, [hasMore, isLoading, isLoadingMore, loadMoreNotifications, notifications.length])

    const handleMarkAllAsRead = async () => {
        try {
            setIsMarkingAll(true)
            await notificationsApi.markAllAsRead()
            setNotifications((currentNotifications) =>
                currentNotifications.map((notificationItem) => ({
                    ...notificationItem,
                    is_read: true
                }))
            )
        } catch (error) {
            console.error('Failed to mark all as read:', error)
        } finally {
            setIsMarkingAll(false)
        }
    }

    const handleNotificationClick = async (notification: Notification) => {
        try {
            if (!notification.is_read) {
                await notificationsApi.markAsRead(notification.id)
                setNotifications((currentNotifications) =>
                    currentNotifications.map((notificationItem) =>
                        notificationItem.id === notification.id
                            ? { ...notificationItem, is_read: true }
                            : notificationItem
                    )
                )
            }

            if (notification.link) {
                router.push(notification.link)
            }
        } catch (error) {
            console.error('Failed to mark notification as read:', error)
        }
    }

    // Filter notifications based on selected filter
    const filteredNotifications = notifications.filter((n) => {
        if (filter === 'unread') return !n.is_read
        if (filter === 'read') return n.is_read
        return true
    })

    const unreadCount = notifications.filter((n) => !n.is_read).length

    return (
        <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                    <h3 className="text-lg font-medium">Notification History</h3>
                    <p className="text-sm text-muted-foreground">
                        Recent activity from your pipelines and datasets.
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    {/* Filter pills */}
                    <div className="flex items-center gap-1 rounded-lg border bg-muted/50 p-1">
                        <button
                            onClick={() => setFilter('all')}
                            className={cn(
                                "px-3 py-1 text-xs font-medium rounded-md transition-colors",
                                filter === 'all'
                                    ? "bg-background shadow-sm"
                                    : "text-muted-foreground hover:text-foreground"
                            )}
                        >
                            All
                        </button>
                        <button
                            onClick={() => setFilter('unread')}
                            className={cn(
                                "px-3 py-1 text-xs font-medium rounded-md transition-colors flex items-center gap-1",
                                filter === 'unread'
                                    ? "bg-background shadow-sm"
                                    : "text-muted-foreground hover:text-foreground"
                            )}
                        >
                            Unread
                            {unreadCount > 0 && (
                                <span className="inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-blue-600 px-1 text-[10px] text-white">
                                    {unreadCount}
                                </span>
                            )}
                        </button>
                        <button
                            onClick={() => setFilter('read')}
                            className={cn(
                                "px-3 py-1 text-xs font-medium rounded-md transition-colors",
                                filter === 'read'
                                    ? "bg-background shadow-sm"
                                    : "text-muted-foreground hover:text-foreground"
                            )}
                        >
                            Read
                        </button>
                    </div>
                    {/* Mark all as read button */}
                    {unreadCount > 0 && (
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={handleMarkAllAsRead}
                            disabled={isMarkingAll || isLoading}
                            className="gap-2"
                        >
                            {isMarkingAll ? (
                                <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                                <CheckCheck className="h-4 w-4" />
                            )}
                            <span className="hidden sm:inline">Mark all as read</span>
                        </Button>
                    )}
                </div>
            </div>

            <div className="rounded-lg border bg-card text-card-foreground shadow-sm">
                {isLoading && notifications.length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                        <Loader2 className="h-6 w-6 animate-spin text-blue-500 mb-2" />
                        <p className="text-sm">Loading notifications...</p>
                    </div>
                ) : filteredNotifications.length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                        <div className="rounded-full bg-slate-100 p-3 dark:bg-slate-800 mb-3">
                            <Bell className="h-6 w-6 text-slate-400" />
                        </div>
                        <h3 className="font-medium text-foreground">
                            {filter === 'unread' ? 'No unread notifications' :
                                filter === 'read' ? 'No read notifications' :
                                    'No notifications yet'}
                        </h3>
                        <p className="text-sm mt-1">
                            {filter !== 'all' ? 'Try a different filter.' : 'Activity will show up here.'}
                        </p>
                    </div>
                ) : (
                    <div
                        ref={scrollContainerRef}
                        onScroll={handleScroll}
                        className="max-h-[420px] overflow-y-auto sm:max-h-[520px]"
                    >
                        <div className="divide-y">
                            {filteredNotifications.map((notification) => (
                                <div
                                    key={notification.id}
                                    onClick={() => handleNotificationClick(notification)}
                                    className={cn(
                                        "group flex cursor-pointer items-start gap-4 p-4 transition-colors hover:bg-slate-50 dark:hover:bg-slate-800/50",
                                        !notification.is_read && "bg-blue-50/40 dark:bg-blue-900/10"
                                    )}
                                >


                                    <div className="flex-1 min-w-0 space-y-1">
                                        <div className="flex items-center justify-between gap-2">
                                            <p
                                                className={cn(
                                                    "text-sm font-medium",
                                                    !notification.is_read &&
                                                    "text-blue-700 dark:text-blue-400"
                                                )}
                                            >
                                                {notification.title}
                                            </p>
                                            <span className="shrink-0 text-xs text-muted-foreground whitespace-nowrap">
                                                {formatDistanceToNow(
                                                    new Date(notification.created_at),
                                                    { addSuffix: true }
                                                )}
                                            </span>
                                        </div>
                                        <p className="text-xs text-muted-foreground line-clamp-2 leading-relaxed">
                                            {notification.message}
                                        </p>

                                        {notification.link && (
                                            <div className="flex items-center gap-1 text-xs font-medium text-blue-600 dark:text-blue-400 mt-1.5 opacity-0 transition-opacity group-hover:opacity-100">
                                                <span>View details</span>
                                                <ExternalLink className="h-3 w-3" />
                                            </div>
                                        )}
                                    </div>

                                    {!notification.is_read && (
                                        <div className="mt-1.5 h-2 w-2 rounded-full bg-blue-600 shrink-0" />
                                    )}
                                </div>
                            ))}
                        </div>
                        {hasMore && (
                            <div className="flex items-center justify-center gap-2 border-t py-3 text-xs text-muted-foreground">
                                {isLoadingMore ? (
                                    <>
                                        <Loader2 className="h-4 w-4 animate-spin" />
                                        Loading more notifications...
                                    </>
                                ) : (
                                    <span>Scroll to load more</span>
                                )}
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    )
}
