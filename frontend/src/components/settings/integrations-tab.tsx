'use client'

import { useState, useEffect } from 'react'
import { Save, Loader2 } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { useToast } from '@/components/ui/use-toast'
import { settingsApi } from '@/lib/api'
import type { ApplicationSettings } from '@/types'

export function IntegrationsTab() {
  const [settings, setSettings] = useState<ApplicationSettings | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const { toast } = useToast()

  useEffect(() => {
    loadSettings()
  }, [])

  const loadSettings = async () => {
    try {
      const data = await settingsApi.get()
      setSettings(data)
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
      await settingsApi.update(settings)
      toast({ title: 'Settings saved successfully' })
    } catch (error) {
      toast({ title: 'Failed to save settings', variant: 'destructive' })
    } finally {
      setSaving(false)
    }
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
      {/* SonarQube */}
      <Card>
        <CardHeader>
          <CardTitle>SonarQube</CardTitle>
          <CardDescription>Code quality and security analysis</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <Label htmlFor="sonar-enabled">Enable SonarQube</Label>
            <Switch
              id="sonar-enabled"
              checked={settings.sonarqube.enabled}
              onCheckedChange={(checked) =>
                setSettings({ ...settings, sonarqube: { ...settings.sonarqube, enabled: checked } })
              }
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="sonar-url">Host URL</Label>
            <Input
              id="sonar-url"
              value={settings.sonarqube.host_url}
              onChange={(e) =>
                setSettings({ ...settings, sonarqube: { ...settings.sonarqube, host_url: e.target.value } })
              }
              placeholder="http://localhost:9000"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="sonar-token">Authentication Token</Label>
            <Input
              id="sonar-token"
              type="password"
              value={settings.sonarqube.token || ''}
              onChange={(e) =>
                setSettings({ ...settings, sonarqube: { ...settings.sonarqube, token: e.target.value } })
              }
              placeholder="Enter token to update"
            />
          </div>
        </CardContent>
      </Card>

      {/* CircleCI */}
      <Card>
        <CardHeader>
          <CardTitle>CircleCI</CardTitle>
          <CardDescription>CircleCI integration</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <Label htmlFor="circleci-enabled">Enable CircleCI</Label>
            <Switch
              id="circleci-enabled"
              checked={settings.circleci.enabled}
              onCheckedChange={(checked) =>
                setSettings({ ...settings, circleci: { ...settings.circleci, enabled: checked } })
              }
            />
          </div>
        </CardContent>
      </Card>

      {/* Travis CI */}
      <Card>
        <CardHeader>
          <CardTitle>Travis CI</CardTitle>
          <CardDescription>Travis CI integration</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <Label htmlFor="travis-enabled">Enable Travis CI</Label>
            <Switch
              id="travis-enabled"
              checked={settings.travis.enabled}
              onCheckedChange={(checked) =>
                setSettings({ ...settings, travis: { ...settings.travis, enabled: checked } })
              }
            />
          </div>
        </CardContent>
      </Card>

      {/* Trivy Security Scanner */}
      <Card>
        <CardHeader>
          <CardTitle>Trivy Security Scanner</CardTitle>
          <CardDescription>Container and dependency security scanning</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <Label htmlFor="trivy-enabled">Enable Trivy</Label>
            <Switch
              id="trivy-enabled"
              checked={settings.trivy.enabled}
              onCheckedChange={(checked) =>
                setSettings({ ...settings, trivy: { ...settings.trivy, enabled: checked } })
              }
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="trivy-severity">Severity Levels</Label>
            <Input
              id="trivy-severity"
              value={settings.trivy.severity}
              onChange={(e) =>
                setSettings({ ...settings, trivy: { ...settings.trivy, severity: e.target.value } })
              }
              placeholder="CRITICAL,HIGH,MEDIUM"
            />
          </div>
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
