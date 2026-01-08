'use client'

import { useState, useEffect } from 'react'
import { Save, Loader2, AlertTriangle } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { useToast } from '@/components/ui/use-toast'
import { settingsApi, usersApi } from '@/lib/api'
import type { ApplicationSettings, UserAccount, EmailNotificationTypeToggles } from '@/types'

// Notification type toggle definitions grouped by category
const NOTIFICATION_CATEGORIES = [
  {
    category: 'Model Pipeline',
    description: 'Feature extraction and prediction notifications',
    toggles: [
      {
        key: 'pipeline_completed' as const,
        label: 'Pipeline Completed',
        description: 'Email when feature extraction completes successfully',
      },
      {
        key: 'pipeline_failed' as const,
        label: 'Pipeline Failed',
        description: 'Email when feature extraction pipeline fails',
        isCritical: true,
      },
    ],
  },
  {
    category: 'Dataset Enrichment',
    description: 'Dataset enrichment notifications',
    toggles: [
      {
        key: 'dataset_enrichment_completed' as const,
        label: 'Enrichment Completed',
        description: 'Email when dataset enrichment process completes',
      },
      {
        key: 'dataset_enrichment_failed' as const,
        label: 'Enrichment Failed',
        description: 'Email when dataset enrichment process fails',
        isCritical: true,
      },
    ],
  },
  {
    category: 'System & Rate Limits',
    description: 'GitHub token rate limits and system alerts',
    toggles: [
      {
        key: 'rate_limit_exhausted' as const,
        label: 'Rate Limit Exhausted',
        description: 'Email when all GitHub tokens have exhausted their quota',
        isCritical: true,
      },
      {
        key: 'system_alerts' as const,
        label: 'System Alerts',
        description: 'Email for important system notifications',
        isCritical: true,
      },
    ],
  },
];

export function NotificationsTab() {
  const [settings, setSettings] = useState<ApplicationSettings | null>(null)
  const [user, setUser] = useState<UserAccount | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const { toast } = useToast()

  useEffect(() => {
    loadSettings()
  }, [])

  const loadSettings = async () => {
    try {
      const [settingsData, userData] = await Promise.all([
        settingsApi.get(),
        usersApi.getCurrentUser(),
      ])
      setSettings(settingsData)
      setUser(userData)
    } catch (error) {
      toast({ title: 'Failed to load settings', variant: 'destructive' })
    } finally {
      setLoading(false)
    }
  }

  const handleSave = async () => {
    if (!settings) return

    setSaving(true)
    try {
      await Promise.all([
        settingsApi.update(settings),
        usersApi.updateCurrentUser({
          notification_email: user?.notification_email || null,
        }),
      ])
      toast({ title: 'Notification settings saved successfully' })
    } catch (error) {
      toast({ title: 'Failed to save settings', variant: 'destructive' })
    } finally {
      setSaving(false)
    }
  }

  const handleToggleChange = (key: keyof EmailNotificationTypeToggles, checked: boolean) => {
    if (!settings) return
    setSettings({
      ...settings,
      notifications: {
        ...settings.notifications,
        email_type_toggles: {
          ...settings.notifications.email_type_toggles,
          [key]: checked,
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

  if (!settings) return null

  return (
    <div className="space-y-6">
      {/* Personal Email Settings */}
      {user && (
        <Card>
          <CardHeader>
            <CardTitle>My Notification Settings</CardTitle>
            <CardDescription>
              Configure how you receive personal notifications.
            </CardDescription>
          </CardHeader>
          <CardContent>
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
          </CardContent>
        </Card>
      )}

      {/* Email Toggle */}
      <Card>
        <CardHeader>
          <CardTitle>Email Notifications</CardTitle>
          <CardDescription>Enable email notifications for system events</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <Label htmlFor="email-enabled">Enable Email Notifications</Label>
            <Switch
              id="email-enabled"
              checked={settings.notifications.email_enabled}
              onCheckedChange={(checked) =>
                setSettings({
                  ...settings,
                  notifications: { ...settings.notifications, email_enabled: checked },
                })
              }
            />
          </div>
          {settings.notifications.email_enabled && (
            <div className="space-y-2">
              <Label htmlFor="email-recipients">Recipients (comma-separated)</Label>
              <Input
                id="email-recipients"
                value={settings.notifications.email_recipients}
                onChange={(e) =>
                  setSettings({
                    ...settings,
                    notifications: { ...settings.notifications, email_recipients: e.target.value },
                  })
                }
                placeholder="user@example.com, admin@example.com"
              />
            </div>
          )}
        </CardContent>
      </Card>

      {/* Email Type Toggles */}
      {settings.notifications.email_enabled && (
        <Card>
          <CardHeader>
            <CardTitle>Email Notification Types</CardTitle>
            <CardDescription>
              Choose which events trigger email notifications to recipients
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {NOTIFICATION_CATEGORIES.map((category) => (
              <div key={category.category} className="space-y-3">
                {/* Category Header */}
                <div className="border-b pb-2">
                  <h4 className="font-semibold text-sm">{category.category}</h4>
                  <p className="text-xs text-muted-foreground">{category.description}</p>
                </div>
                {/* Category Toggles */}
                <div className="space-y-3">
                  {category.toggles.map((toggle) => (
                    <div key={toggle.key} className="flex items-center justify-between py-1 pl-2">
                      <div className="space-y-0.5">
                        <div className="flex items-center gap-2">
                          <Label htmlFor={`toggle-${toggle.key}`}>{toggle.label}</Label>
                          {'isCritical' in toggle && toggle.isCritical && (
                            <span className="inline-flex items-center gap-1 rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700 dark:bg-red-900/30 dark:text-red-400">
                              <AlertTriangle className="h-3 w-3" />
                              Critical
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-muted-foreground">{toggle.description}</p>
                      </div>
                      <Switch
                        id={`toggle-${toggle.key}`}
                        checked={settings.notifications.email_type_toggles?.[toggle.key] ?? false}
                        onCheckedChange={(checked) => handleToggleChange(toggle.key, checked)}
                      />
                    </div>
                  ))}
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
