'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'
import {
  AlertTriangle,
  ArrowLeft,
  BookCopy,
  Calendar,
  Clock,
  Code,
  Github,
  GitPullRequest,
  Hexagon,
  Info,
  Loader2,
  Shield,
  Sparkles,
} from 'lucide-react'
import { ResponsiveContainer, RadialBar, RadialBarChart, Tooltip } from 'recharts'

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { riskApi } from '@/lib/api'
import type { BuildDetail, RiskExplanation } from '@/types'
import { cn } from '@/lib/utils'

interface BuildDetailClientProps {
  build: BuildDetail
}

export function BuildDetailClient({ build }: BuildDetailClientProps) {
  const [explanation, setExplanation] = useState<RiskExplanation | null>(null)
  const [explanationLoading, setExplanationLoading] = useState(true)
  const [explanationError, setExplanationError] = useState<string | null>(null)

  useEffect(() => {
    const loadExplanation = async () => {
      try {
        const data = await riskApi.getRiskExplanation(build.id)
        setExplanation(data)
      } catch (err) {
        console.error(err)
        setExplanationError('Không thể tải giải thích rủi ro.')
      } finally {
        setExplanationLoading(false)
      }
    }

    loadExplanation()
  }, [build.id])

  const riskLevel = explanation?.risk_level ?? build.risk_assessment?.risk_level ?? 'low'
  const riskScore = explanation?.risk_score ?? build.risk_assessment?.risk_score ?? 0
  const uncertainty = explanation?.uncertainty ?? build.risk_assessment?.uncertainty ?? 0

  const coverage = build.sonarqube_result?.coverage ?? 0
  const technicalDebt = build.sonarqube_result?.technical_debt_minutes ?? 0

  const riskChartData = [
    {
      name: 'Risk',
      value: riskScore * 100,
      fill:
        riskLevel === 'low'
          ? '#22c55e'
          : riskLevel === 'medium'
            ? '#f97316'
            : riskLevel === 'high'
              ? '#ea580c'
              : '#ef4444',
    },
  ]

  return (
    <div className="space-y-6">
      <Link
        href="/builds"
        className="inline-flex items-center gap-2 text-sm font-semibold text-blue-600 transition hover:text-blue-700"
      >
        <ArrowLeft className="h-4 w-4" />
        Quay lại danh sách builds
      </Link>

      <Card>
        <CardHeader className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <CardTitle className="flex items-center gap-3 text-xl">
              <Hexagon className="h-6 w-6 text-blue-500" />
              {build.repository}
            </CardTitle>
            <CardDescription>
              Workflow: {build.workflow_name} · Branch: {build.branch} · Build {build.build_number}
            </CardDescription>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <span
              className={cn(
                'inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-semibold uppercase',
                riskLevel === 'low' && 'bg-emerald-100 text-emerald-700',
                riskLevel === 'medium' && 'bg-amber-100 text-amber-700',
                riskLevel === 'high' && 'bg-orange-100 text-orange-700',
                riskLevel === 'critical' && 'bg-red-100 text-red-700',
              )}
            >
              <AlertTriangle className="h-4 w-4" />
              {riskLevel} risk
            </span>
            <a
              href={build.url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-2 rounded-full border border-slate-200 px-3 py-1 text-xs font-semibold text-slate-700 transition hover:border-blue-500 hover:text-blue-600"
            >
              <Github className="h-4 w-4" />
              View on GitHub
            </a>
          </div>
        </CardHeader>
        <CardContent className="grid gap-6 md:grid-cols-[2fr_1fr]">
          <div className="grid gap-4">
            <div className="rounded-xl border border-blue-200 bg-blue-50/60 p-4 text-sm dark:border-blue-900/70 dark:bg-blue-950/40">
              {explanationLoading ? (
                <div className="flex items-center gap-2 text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Đang phân tích giải thích Bayesian...
                </div>
              ) : explanationError ? (
                <p className="text-red-600 dark:text-red-300">{explanationError}</p>
              ) : explanation ? (
                <>
                  <p className="flex items-center gap-2 text-slate-800 dark:text-slate-100">
                    <Sparkles className="h-4 w-4 text-blue-600" />
                    {explanation.summary}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    Độ tin cậy: {explanation.confidence} · Mô hình {explanation.model_version ?? 'mock-0.1.0'}
                  </p>
                </>
              ) : null}
            </div>
            <div className="grid gap-3 rounded-xl border bg-white/60 p-4 dark:bg-slate-900/60 md:grid-cols-3">
              <InfoItem icon={<Calendar className="h-5 w-5 text-blue-500" />} label="Started">
                {build.started_at ? new Date(build.started_at).toLocaleString('vi-VN') : 'N/A'}
              </InfoItem>
              <InfoItem icon={<Clock className="h-5 w-5 text-purple-500" />} label="Duration">
                {build.duration_seconds ? `${Math.round(build.duration_seconds / 60)} phút` : 'Đang chạy'}
              </InfoItem>
              <InfoItem icon={<GitPullRequest className="h-5 w-5 text-emerald-500" />} label="Commit author">
                {build.author_name}
              </InfoItem>
            </div>

            <div className="rounded-xl border bg-white/60 p-4 dark:bg-slate-900/60">
              <h3 className="text-sm font-semibold text-slate-700">Commit summary</h3>
              <p className="text-xs text-muted-foreground">
                Commit SHA: {build.commit_sha} · Email: {build.author_email}
              </p>
              <div className="mt-3 grid gap-3 md:grid-cols-2">
                <div className="rounded-lg border border-slate-100 bg-white p-3 text-xs dark:border-slate-800 dark:bg-slate-900">
                  <p className="font-semibold text-slate-700">Key changes</p>
                  <ul className="mt-2 space-y-1 text-muted-foreground">
                    <li>- Update pipeline security hooks</li>
                    <li>- Adjust model inference config</li>
                    <li>- Refactor GitHub sync worker</li>
                  </ul>
                </div>
                <div className="rounded-lg border border-slate-100 bg-white p-3 text-xs dark:border-slate-800 dark:bg-slate-900">
                  <p className="font-semibold text-slate-700">Risk indicators</p>
                  <ul className="mt-2 space-y-1 text-muted-foreground">
                    <li>- 12 files changed · 420 lines added</li>
                    <li>- Touches critical module: `collector`</li>
                    <li>- Pending review from security team</li>
                  </ul>
                </div>
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <Card className="border border-slate-200 shadow-none dark:border-slate-800">
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-semibold">SonarQube quality metrics</CardTitle>
                  <CardDescription>Quality gate: {build.sonarqube_result?.quality_gate_status}</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3 text-xs">
                  <MetricRow label="Coverage" value={`${coverage}%`} intent="positive" />
                  <MetricRow label="Code smells" value={build.sonarqube_result?.code_smells ?? 0} />
                  <MetricRow label="Bugs" value={build.sonarqube_result?.bugs ?? 0} />
                  <MetricRow label="Vulnerabilities" value={build.sonarqube_result?.vulnerabilities ?? 0} />
                  <MetricRow label="Technical debt" value={`${technicalDebt} phút`} />
                </CardContent>
              </Card>
              <Card className="border border-slate-200 shadow-none dark:border-slate-800">
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-semibold">Security review notes</CardTitle>
                  <CardDescription>BuildGuard hiện theo dõi bảo mật thông qua SonarQube và risk score.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3 text-xs">
                  <MetricRow
                    label="High risk touchpoints"
                    value={build.risk_assessment?.risk_level === 'high' || build.risk_assessment?.risk_level === 'critical' ? 'Review required' : 'Stable'}
                    intent={build.risk_assessment?.risk_level === 'high' || build.risk_assessment?.risk_level === 'critical' ? 'attention' : 'positive'}
                  />
                  <p className="text-muted-foreground">
                    Sử dụng SonarQube để xem chi tiết các issue bảo mật và chất lượng code. Module Trivy đã được loại bỏ khỏi bản
                    prototype này để đơn giản hóa pipeline.
                  </p>
                </CardContent>
              </Card>
            </div>
          </div>

          <div className="space-y-4">
            <Card className="border border-slate-200 shadow-none dark:border-slate-800">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-semibold">Risk score</CardTitle>
                <CardDescription>Được tính bởi Bayesian CNN (demo dữ liệu giả lập)</CardDescription>
              </CardHeader>
              <CardContent className="h-56">
                <ResponsiveContainer width="100%" height="100%">
                  <RadialBarChart
                    cx="50%"
                    cy="50%"
                    innerRadius="40%"
                    outerRadius="90%"
                    barSize={22}
                    data={riskChartData}
                  >
                    <RadialBar minAngle={15} background clockWise dataKey="value" cornerRadius={10} />
                    <Tooltip formatter={(value: number) => [`${value.toFixed(1)}%`, 'Risk score']} />
                  </RadialBarChart>
                </ResponsiveContainer>
            <div className="mt-2 text-center text-sm text-muted-foreground">
              Điểm rủi ro:{' '}
              <span className="font-semibold text-slate-900">{riskScore.toFixed(2)}</span> · Độ bất định: {uncertainty.toFixed(2)}
            </div>
            {explanation ? (
              <div className="mt-3 space-y-2 text-xs text-muted-foreground">
                {explanation.drivers.slice(0, 3).map((driver) => (
                  <div
                    key={driver.key}
                    className="flex items-center justify-between rounded-lg border border-slate-100 bg-white px-2 py-1 dark:border-slate-800 dark:bg-slate-900"
                  >
                    <span className="font-semibold text-slate-700 dark:text-slate-100">{driver.label}</span>
                    <span>{Math.round(driver.contribution * 100)}%</span>
                  </div>
                ))}
              </div>
            ) : null}
          </CardContent>
        </Card>

            <Card className="border border-slate-200 shadow-none dark:border-slate-800">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-semibold">Deployment readiness</CardTitle>
                <CardDescription>Khuyến nghị dựa trên rule-based + risk score</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3 text-xs">
                {explanation?.recommended_actions ? (
                  explanation.recommended_actions.map((action, index) => (
                    <RecommendationItem
                      key={action}
                      icon={<Sparkles className="h-4 w-4 text-blue-500" />}
                      title={`Khuyến nghị ${index + 1}`}
                      description={action}
                    />
                  ))
                ) : (
                  <>
                    <RecommendationItem
                      icon={<Shield className="h-4 w-4 text-emerald-500" />}
                      title="Policy check"
                      description="Yêu cầu approval bổ sung từ DevSecOps trước khi deploy."
                    />
                    <RecommendationItem
                      icon={<BookCopy className="h-4 w-4 text-blue-500" />}
                      title="Documentation"
                      description="Cập nhật change log và lý do thay đổi pipeline security."
                    />
                    <RecommendationItem
                      icon={<Code className="h-4 w-4 text-purple-500" />}
                      title="Tests"
                      description="Chạy lại integration tests cho module GitHub collector và ML adapters."
                    />
                  </>
                )}
              </CardContent>
            </Card>

            <Card className="border border-slate-200 shadow-none dark:border-slate-800">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-semibold">Timeline đồng bộ GitHub</CardTitle>
                <CardDescription>Quá trình thu thập dữ liệu build (demo)</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3 text-xs">
                {explanation ? (
                  <div className="grid gap-2 sm:grid-cols-2">
                    {Object.entries(explanation.feature_breakdown).map(([name, value]) => (
                      <div key={name} className="rounded-lg border border-slate-100 bg-slate-50 p-2 text-slate-700 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200">
                        <p className="text-[11px] uppercase text-muted-foreground">{name}</p>
                        <p className="text-lg font-semibold">{value.toFixed(1)}%</p>
                      </div>
                    ))}
                  </div>
                ) : null}
                <TimelineItem
                  time="T-12m"
                  label="Workflow run completed"
                  detail="GitHub Actions kết thúc · trạng thái: success"
                />
                <TimelineItem
                  time="T-9m"
                  label="Collector synced logs"
                  detail="Thu thập logs & artifacts · 3 warnings ghi nhận"
                />
                <TimelineItem
                  time="T-6m"
                  label="Feature extraction"
                  detail="Tạo feature vector cho Bayesian CNN · 128 features"
                />
                <TimelineItem
                  time="T-2m"
                  label="Risk scoring"
                  detail={`Bayesian CNN dự đoán risk=${riskScore.toFixed(2)} · uncertainty=${uncertainty.toFixed(2)}`}
                />
              </CardContent>
            </Card>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

interface InfoItemProps {
  icon: React.ReactNode
  label: string
  children: React.ReactNode
}

function InfoItem({ icon, label, children }: InfoItemProps) {
  return (
    <div className="flex items-start gap-3 rounded-lg border border-slate-200 bg-white p-3 text-xs dark:border-slate-800 dark:bg-slate-900">
      <div className="mt-1">{icon}</div>
      <div>
        <p className="text-xs font-semibold uppercase text-muted-foreground">{label}</p>
        <p className="text-sm text-slate-700 dark:text-slate-200">{children}</p>
      </div>
    </div>
  )
}

interface MetricRowProps {
  label: string
  value: string | number
  intent?: 'positive' | 'negative' | 'attention'
}

function MetricRow({ label, value, intent }: MetricRowProps) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-muted-foreground">{label}</span>
      <span
        className={cn(
          'font-semibold',
          intent === 'positive' && 'text-emerald-600',
          intent === 'negative' && 'text-red-600',
          intent === 'attention' && 'text-amber-600',
        )}
      >
        {value}
      </span>
    </div>
  )
}

interface RecommendationItemProps {
  icon: React.ReactNode
  title: string
  description: string
}

function RecommendationItem({ icon, title, description }: RecommendationItemProps) {
  return (
    <div className="flex items-start gap-3 rounded-lg border border-slate-100 bg-white p-3 dark:border-slate-800 dark:bg-slate-900">
      <div className="mt-1">{icon}</div>
      <div>
        <p className="text-sm font-semibold">{title}</p>
        <p className="text-xs text-muted-foreground">{description}</p>
      </div>
    </div>
  )
}

interface TimelineItemProps {
  time: string
  label: string
  detail: string
}

function TimelineItem({ time, label, detail }: TimelineItemProps) {
  return (
    <div className="flex gap-3 rounded-lg border border-slate-100 bg-white p-3 dark:border-slate-800 dark:bg-slate-900">
      <div className="font-mono text-xs text-blue-600">{time}</div>
      <div>
        <p className="text-sm font-semibold">{label}</p>
        <p className="text-xs text-muted-foreground">{detail}</p>
      </div>
    </div>
  )
}
