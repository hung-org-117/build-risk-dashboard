'use client'

import { useState, useEffect } from 'react'
import { Save, Loader2, AlertTriangle } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { useToast } from '@/components/ui/use-toast'
import { usersApi } from '@/lib/api'
import type { UserAccount, NotificationSubscription } from '@/types'

// Notification types available to regular users
const USER_NOTIFICATION_TYPES = [
  {
    key: 'high_risk_detected',
    label: 'High Risk Detected',
    description: 'Get notified when a high-risk build is detected in your repositories',
    isCritical: true,
  },
  {
    key: 'build_prediction_ready',
    label: 'Build Prediction Ready',
    description: 'Get notified when build predictions are complete',
  },
];

// Additional notification types available to admins
const ADMIN_NOTIFICATION_TYPES = [
  {
    category: 'Model Pipeline',
    description: 'Feature extraction and prediction notifications',
    toggles: [
      {
        key: 'pipeline_completed',
        label: 'Pipeline Completed',
        description: 'Notify when feature extraction completes successfully',
      },
      {
        key: 'pipeline_failed',
        label: 'Pipeline Failed',
        description: 'Notify when feature extraction pipeline fails',
        isCritical: true,
      },
    ],
  },
  {
    category: 'Dataset Enrichment',
    description: 'Dataset enrichment notifications',
    toggles: [
      {
        key: 'dataset_enrichment_completed',
        label: 'Enrichment Completed',
        description: 'Notify when dataset enrichment process completes',
      },
      {
        key: 'dataset_enrichment_failed',
        label: 'Enrichment Failed',
        description: 'Notify when dataset enrichment process fails',
        isCritical: true,
      },
    ],
  },
  {
    category: 'System & Rate Limits',
    description: 'GitHub token rate limits and system alerts',
    toggles: [
      {
        key: 'rate_limit_exhausted',
        label: 'Rate Limit Exhausted',
        description: 'Notify when all GitHub tokens have exhausted their quota',
        isCritical: true,
      },
      {
        key: 'system_alerts',
        label: 'System Alerts',
        description: 'Important system notifications',
        isCritical: true,
      },
    ],
  },
];

export function NotificationsTab() {
  const [user, setUser] = useState<UserAccount | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const { toast } = useToast()

  const isAdmin = user?.role === 'admin'

  useEffect(() => {
    loadUser()
  }, [])

  const loadUser = async () => {
    try {
      const userData = await usersApi.getCurrentUser()
      setUser(userData)
    } catch (error) {
      toast({ title: 'Failed to load settings', variant: 'destructive' })
    } finally {
      setLoading(false)
    }
  }

  const handleSave = async () => {
    if (!user) return

    setSaving(true)
    try {
      await usersApi.updateCurrentUser({
        notification_email: user.notification_email || null,
        browser_notifications: user.browser_notifications,
        email_notifications_enabled: user.email_notifications_enabled,
        subscriptions: user.subscriptions,
      })
      toast({ title: 'Notification settings saved successfully' })
    } catch (error) {
      toast({ title: 'Failed to save settings', variant: 'destructive' })
    } finally {
      setSaving(false)
    }
  }

  const handleSubscriptionChange = (
    key: string,
    channel: keyof NotificationSubscription,
    checked: boolean
  ) => {
    if (!user) return

    const currentSub = user.subscriptions[key] || { in_app: true, email: false }
    setUser({
      ...user,
      subscriptions: {
        ...user.subscriptions,
        [key]: {
          ...currentSub,
          [channel]: checked,
        },
      },
    })
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <Loader2 className="h-6 w-6 animate-spin" />
      </div>
    )
  }

  if (!user) return null

  return (
    <div className="space-y-6">
      {/* Personal Email Settings */}
      <Card>
        <CardHeader>
          <CardTitle>My Notification Settings</CardTitle>
          <CardDescription>
            Configure how you receive notifications.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="personal-email">Notification Email</Label>
            <Input
              id="personal-email"
              value={user.notification_email || ''}
              onChange={(e) =>
                setUser({
                  ...user,
                  notification_email: e.target.value,
                })
              }
              placeholder={user.email}
            />
            <p className="text-sm text-muted-foreground">
              Leave empty to use your default email address ({user.email}).
            </p>
          </div>

          <div className="flex items-center justify-between pt-2">
            <div>
              <Label htmlFor="browser-notifications">Browser Notifications</Label>
              <p className="text-sm text-muted-foreground">Show browser notifications for events</p>
            </div>
            <Switch
              id="browser-notifications"
              checked={user.browser_notifications}
              onCheckedChange={(checked) =>
                setUser({ ...user, browser_notifications: checked })
              }
            />
          </div>

          <div className="flex items-center justify-between">
            <div>
              <Label htmlFor="email-notifications">Email Notifications</Label>
              <p className="text-sm text-muted-foreground">Send email notifications for events</p>
            </div>
            <Switch
              id="email-notifications"
              checked={user.email_notifications_enabled}
              onCheckedChange={(checked) =>
                setUser({ ...user, email_notifications_enabled: checked })
              }
            />
          </div>
        </CardContent>
      </Card>

      {/* User Notification Types */}
      <Card>
        <CardHeader>
          <CardTitle>Notification Preferences</CardTitle>
          <CardDescription>
            Choose which events you want to be notified about
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {USER_NOTIFICATION_TYPES.map((type) => {
            const sub = user.subscriptions[type.key] || { in_app: true, email: false }
            return (
              <div key={type.key} className="flex items-center justify-between py-2 border-b last:border-0">
                <div className="space-y-0.5">
                  <div className="flex items-center gap-2">
                    <Label>{type.label}</Label>
                    {'isCritical' in type && type.isCritical && (
                      <span className="inline-flex items-center gap-1 rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700 dark:bg-red-900/30 dark:text-red-400">
                        <AlertTriangle className="h-3 w-3" />
                        Critical
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground">{type.description}</p>
                </div>
                <div className="flex gap-4">
                  <div className="flex items-center gap-2">
                    <Label htmlFor={`${type.key}-inapp`} className="text-xs text-muted-foreground">In-App</Label>
                    <Switch
                      id={`${type.key}-inapp`}
                      checked={sub.in_app}
                      onCheckedChange={(checked) => handleSubscriptionChange(type.key, 'in_app', checked)}
                    />
                  </div>
                  <div className="flex items-center gap-2">
                    <Label htmlFor={`${type.key}-email`} className="text-xs text-muted-foreground">Email</Label>
                    <Switch
                      id={`${type.key}-email`}
                      checked={sub.email}
                      disabled={!user.email_notifications_enabled}
                      onCheckedChange={(checked) => handleSubscriptionChange(type.key, 'email', checked)}
                    />
                  </div>
                </div>
              </div>
            )
          })}
        </CardContent>
      </Card>

      {/* Admin-only Notification Types */}
      {isAdmin && (
        <Card>
          <CardHeader>
            <CardTitle>Admin Notifications</CardTitle>
            <CardDescription>
              System and pipeline notifications (admin only)
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {ADMIN_NOTIFICATION_TYPES.map((category) => (
              <div key={category.category} className="space-y-3">
                {/* Category Header */}
                <div className="border-b pb-2">
                  <h4 className="font-semibold text-sm">{category.category}</h4>
                  <p className="text-xs text-muted-foreground">{category.description}</p>
                </div>
                {/* Category Toggles */}
                <div className="space-y-3">
                  {category.toggles.map((toggle) => {
                    const sub = user.subscriptions[toggle.key] || { in_app: true, email: false }
                    return (
                      <div key={toggle.key} className="flex items-center justify-between py-1 pl-2">
                        <div className="space-y-0.5">
                          <div className="flex items-center gap-2">
                            <Label>{toggle.label}</Label>
                            {'isCritical' in toggle && toggle.isCritical && (
                              <span className="inline-flex items-center gap-1 rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700 dark:bg-red-900/30 dark:text-red-400">
                                <AlertTriangle className="h-3 w-3" />
                                Critical
                              </span>
                            )}
                          </div>
                          <p className="text-xs text-muted-foreground">{toggle.description}</p>
                        </div>
                        <div className="flex gap-4">
                          <div className="flex items-center gap-2">
                            <Label htmlFor={`${toggle.key}-inapp`} className="text-xs text-muted-foreground">In-App</Label>
                            <Switch
                              id={`${toggle.key}-inapp`}
                              checked={sub.in_app}
                              onCheckedChange={(checked) => handleSubscriptionChange(toggle.key, 'in_app', checked)}
                            />
                          </div>
                          <div className="flex items-center gap-2">
                            <Label htmlFor={`${toggle.key}-email`} className="text-xs text-muted-foreground">Email</Label>
                            <Switch
                              id={`${toggle.key}-email`}
                              checked={sub.email}
                              disabled={!user.email_notifications_enabled}
                              onCheckedChange={(checked) => handleSubscriptionChange(toggle.key, 'email', checked)}
                            />
                          </div>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      <div className="flex justify-end">
        <Button onClick={handleSave} disabled={saving}>
          {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
          Save Changes
        </Button>
      </div>
    </div>
  )
}
