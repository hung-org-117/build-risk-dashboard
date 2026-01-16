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


export function NotificationsTab() {
  const [user, setUser] = useState<UserAccount | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const { toast } = useToast()

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

      {/* User Notification Types - Email Preferences */}
      <Card>
        <CardHeader>
          <CardTitle>Email Notifications for Events</CardTitle>
          <CardDescription>
            All events are shown in-app by default. Configure which events should also be sent via email.
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
                <div className="flex items-center gap-2">
                  <Label htmlFor={`${type.key}-email`} className="text-xs text-muted-foreground">Send Email</Label>
                  <Switch
                    id={`${type.key}-email`}
                    checked={sub.email}
                    disabled={!user.email_notifications_enabled}
                    onCheckedChange={(checked) => handleSubscriptionChange(type.key, 'email', checked)}
                  />
                </div>
              </div>
            )
          })}
        </CardContent>
      </Card>



      <div className="flex justify-end">
        <Button onClick={handleSave} disabled={saving}>
          {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
          Save Changes
        </Button>
      </div>
    </div>
  )
}
