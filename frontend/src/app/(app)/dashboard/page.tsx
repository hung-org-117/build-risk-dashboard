'use client'

import { useEffect, useMemo, useState } from 'react'
import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { AlertCircle, ArrowUpRight, Flame, ShieldCheck, Timer, Workflow } from 'lucide-react'

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { dashboardApi } from '@/lib/api'
import { cn } from '@/lib/utils'
import type { DashboardSummaryResponse, RiskLevel } from '@/types'

const CONCLUSION_LABELS: Record<string, string> = {
  success: 'Thành công',
  failure: 'Thất bại',
  neutral: 'Trung tính',
  cancelled: 'Đã hủy',
}

const RISK_LABEL_CLASSES: Record<RiskLevel, string> = {
  low: 'bg-emerald-100 text-emerald-700',
  medium: 'bg-amber-100 text-amber-700',
  high: 'bg-orange-100 text-orange-700',
  critical: 'bg-red-100 text-red-700',
}

export default function DashboardPage() {
  const [summary, setSummary] = useState<DashboardSummaryResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchSummary = async () => {
      try {
        const data = await dashboardApi.getSummary()
        setSummary(data)
      } catch (err) {
        console.error(err)
        setError('Không thể tải dữ liệu dashboard. Vui lòng kiểm tra backend API.')
      } finally {
        setLoading(false)
      }
    }

    fetchSummary()
  }, [])

  const trendData = useMemo(
    () =>
      summary?.trends.map((trend) => ({
        date: trend.date,
        builds: trend.builds,
        riskScore: trend.risk_score,
        failures: trend.failures,
      })) ?? [],
    [summary],
  )

  const repoDistribution = summary?.repo_distribution ?? []
  const riskHeatmap = summary?.risk_heatmap ?? []
  const highRiskBuilds = summary?.high_risk_builds ?? []
  const metrics = summary?.metrics
  const riskCounts = metrics?.risk_distribution ?? { low: 0, medium: 0, high: 0, critical: 0 }

  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle>Đang tải dashboard...</CardTitle>
            <CardDescription>Kết nối tới API backend để lấy dữ liệu tổng hợp.</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">Vui lòng chờ trong giây lát.</p>
          </CardContent>
        </Card>
      </div>
    )
  }

  if (error || !summary || !metrics) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <Card className="w-full max-w-md border-red-200 bg-red-50/50 dark:border-red-800 dark:bg-red-900/20">
          <CardHeader>
            <CardTitle className="text-red-600 dark:text-red-300">Không thể tải dữ liệu</CardTitle>
            <CardDescription>{error ?? 'Dữ liệu dashboard chưa sẵn sàng.'}</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              Kiểm tra backend FastAPI và đảm bảo endpoint <code>/api/dashboard/summary</code> hoạt động.
            </p>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <SummaryCard
          icon={<Workflow className="h-6 w-6 text-blue-500" />}
          title="Tổng số builds (14 ngày)"
          value={metrics.total_builds}
          sublabel={`${repoDistribution.length} repositories`}
        />
        <SummaryCard
          icon={<ShieldCheck className="h-6 w-6 text-emerald-500" />}
          title="Điểm rủi ro trung bình"
          value={metrics.average_risk_score}
          format="score"
          sublabel={`${riskCounts.low ?? 0} builds an toàn`}
        />
        <SummaryCard
          icon={<Timer className="h-6 w-6 text-purple-500" />}
          title="Thời gian build trung bình"
          value={Math.round(metrics.average_duration_minutes)}
          format="minutes"
          sublabel="Dựa trên builds hoàn thành"
        />
        <SummaryCard
          icon={<Flame className="h-6 w-6 text-red-500" />}
          title="Tỷ lệ thành công"
          value={metrics.success_rate}
          format="percentage"
          sublabel={`${(riskCounts.high ?? 0) + (riskCounts.critical ?? 0)} builds cần chú ý`}
        />
      </section>

      <section className="grid gap-6 lg:grid-cols-[2fr_1fr]">
        <Card className="overflow-hidden">
          <CardHeader className="flex flex-row items-center justify-between gap-2">
            <div>
              <CardTitle>Xu hướng rủi ro & builds</CardTitle>
              <CardDescription>Điểm rủi ro trung bình và số lượng build hoàn thành theo ngày</CardDescription>
            </div>
            <span className="inline-flex items-center gap-1 rounded-full bg-blue-100 px-3 py-1 text-xs font-medium text-blue-600 dark:bg-blue-900/30 dark:text-blue-400">
              <ArrowUpRight className="h-3 w-3" />
              Real-time sync
            </span>
          </CardHeader>
          <CardContent className="h-[280px]">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={trendData}>
                <defs>
                  <linearGradient id="riskGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#ef4444" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="buildGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.35} />
                    <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="date" />
                <YAxis yAxisId="left" orientation="left" stroke="#ef4444" domain={[0, 1]} tickFormatter={(value) => value.toFixed(1)} />
                <YAxis yAxisId="right" orientation="right" stroke="#3b82f6" allowDecimals={false} />
                <Tooltip />
                <Legend />
                <Area yAxisId="left" type="monotone" dataKey="riskScore" stroke="#ef4444" fillOpacity={1} fill="url(#riskGradient)" name="Risk score" />
                <Area
                  yAxisId="right"
                  type="monotone"
                  dataKey="builds"
                  stroke="#3b82f6"
                  fillOpacity={1}
                  fill="url(#buildGradient)"
                  name="Builds"
                />
                <Line yAxisId="right" type="monotone" dataKey="failures" stroke="#f59e0b" name="Failures" strokeWidth={2} dot />
              </AreaChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Heatmap rủi ro (7 ngày)</CardTitle>
            <CardDescription>Phân phối mức rủi ro theo ngày</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-5 gap-2 text-xs">
              <div className="flex flex-col items-start gap-1 text-muted-foreground">
                <span>Ngày</span>
                {riskHeatmap.map((row) => (
                  <span key={row.day} className="h-12 w-full text-sm font-semibold">
                    {row.day}
                  </span>
                ))}
              </div>
              {(['low', 'medium', 'high', 'critical'] as const).map((level) => (
                <div key={level} className="flex flex-col gap-2">
                  <span className="text-xs font-semibold uppercase text-muted-foreground">{level}</span>
                  {riskHeatmap.map((row) => (
                    <div
                      key={`${row.day}-${level}`}
                      className={cn(
                        'flex h-12 items-center justify-center rounded-md border text-sm font-semibold',
                        level === 'low' && 'border-emerald-100 bg-emerald-50 text-emerald-600',
                        level === 'medium' && 'border-amber-100 bg-amber-50 text-amber-600',
                        level === 'high' && 'border-orange-200 bg-orange-50 text-orange-600',
                        level === 'critical' && 'border-red-200 bg-red-50 text-red-600',
                      )}
                    >
                      {row[level]}
                    </div>
                  ))}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
        <Card>
          <CardHeader>
            <CardTitle>Hiệu suất theo repository</CardTitle>
            <CardDescription>Số lượng builds và tỷ lệ build rủi ro cao</CardDescription>
          </CardHeader>
          <CardContent className="h-[240px]">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={repoDistribution}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="repository" tick={{ fontSize: 12 }} />
                <YAxis />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="builds" stroke="#3b82f6" strokeWidth={2} />
                <Line type="monotone" dataKey="highRisk" stroke="#ef4444" strokeWidth={2} strokeDasharray="4 2" />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle>Builds rủi ro cao gần đây</CardTitle>
            <CardDescription>Xem chi tiết để review trước khi deploy</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {highRiskBuilds.map((build) => (
              <div key={build.id} className="rounded-xl border p-3">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="text-sm font-semibold">{build.repository}</p>
                    <p className="text-xs text-muted-foreground">
                      {build.workflow_name} · {build.branch}
                    </p>
                  </div>
                  <span
                    className={cn('rounded-full px-3 py-1 text-xs font-semibold uppercase', RISK_LABEL_CLASSES[build.risk_level])}
                  >
                    {build.risk_level}
                  </span>
                </div>
                <div className="mt-3 flex items-center justify-between text-xs text-muted-foreground">
                  <span>Điểm rủi ro: {build.risk_score.toFixed(2)}</span>
                  <span>
                    Kết luận:{' '}
                    {build.conclusion ? CONCLUSION_LABELS[build.conclusion] ?? build.conclusion : 'Chưa có'}
                  </span>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Sức khỏe pipeline</CardTitle>
            <CardDescription>Đánh giá tổng quan dựa trên SonarQube và risk score Bayesian.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <PipelineHealthItem
              label="Quality Gate SonarQube"
              value="82% đạt chuẩn"
              status="healthy"
              description="9 / 11 builds gần nhất vượt qua quality gate"
            />
            <PipelineHealthItem
              label="Rủi ro ML Assessment"
              value={`${(riskCounts.high ?? 0) + (riskCounts.critical ?? 0)} build cần review`}
              status={(riskCounts.high ?? 0) + (riskCounts.critical ?? 0) > 0 ? 'warning' : 'healthy'}
              description="Dựa trên Bayesian CNN. Xem chi tiết trong bảng High risk builds."
            />
            <PipelineHealthItem
              label="Độ bao phủ code"
              value="64%"
              status="attention"
              description="Mục tiêu >= 75% · Cần bổ sung test cho module ML adapters"
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Các bước tiếp theo</CardTitle>
            <CardDescription>Lộ trình tích hợp đầy đủ BuildGuard platform</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <NextStepsItem
              title="1. Hoàn thiện đồng bộ GitHub"
              description="Hoàn chỉnh background job thu thập workflow runs, commit diff, artifact logs."
            />
            <NextStepsItem
              title="2. Chuẩn hóa dữ liệu huấn luyện"
              description="Xây dựng pipeline trích xuất features, chuẩn bị dataset sạch cho Bayesian CNN."
            />
            <NextStepsItem
              title="3. Tích hợp mô hình AI"
              description="Deploy mô hình Bayesian CNN, kết nối API `/risk` để trả về điểm rủi ro thực."
            />
            <NextStepsItem
              title="4. Alerting & Automation"
              description="Thiết lập cảnh báo Slack/Email và policy tạm dừng deploy cho builds rủi ro cao."
            />
          </CardContent>
        </Card>
      </section>
    </div>
  )
}

interface SummaryCardProps {
  icon: React.ReactNode
  title: string
  value: number
  format?: 'score' | 'percentage' | 'minutes'
  sublabel?: string
}

function SummaryCard({ icon, title, value, format, sublabel }: SummaryCardProps) {
  const formattedValue =
    format === 'score'
      ? value.toFixed(2)
      : format === 'percentage'
        ? `${value.toFixed(1)}%`
        : format === 'minutes'
          ? `${value} phút`
          : value

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">{title}</CardTitle>
        {icon}
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{formattedValue}</div>
        {sublabel ? <p className="text-xs text-muted-foreground">{sublabel}</p> : null}
      </CardContent>
    </Card>
  )
}

interface PipelineHealthItemProps {
  label: string
  value: string
  status: 'healthy' | 'warning' | 'attention'
  description: string
}

function PipelineHealthItem({ label, value, status, description }: PipelineHealthItemProps) {
  return (
    <div className="rounded-xl border bg-white/60 p-4 dark:bg-slate-900/60">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-semibold">{label}</p>
          <p className="text-xs text-muted-foreground">{description}</p>
        </div>
        <div
          className={cn(
            'flex items-center gap-2 rounded-full px-3 py-1 text-sm font-semibold',
            status === 'healthy' && 'bg-emerald-100 text-emerald-700',
            status === 'warning' && 'bg-amber-100 text-amber-700',
            status === 'attention' && 'bg-sky-100 text-sky-700',
          )}
        >
          <AlertCircle className="h-4 w-4" />
          {value}
        </div>
      </div>
    </div>
  )
}

interface NextStepsItemProps {
  title: string
  description: string
}

function NextStepsItem({ title, description }: NextStepsItemProps) {
  return (
    <div className="rounded-xl border bg-white/60 p-4 dark:bg-slate-900/60">
      <p className="text-sm font-semibold">{title}</p>
      <p className="text-xs text-muted-foreground">{description}</p>
    </div>
  )
}
