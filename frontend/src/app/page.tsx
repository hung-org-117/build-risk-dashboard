import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Github, ShieldCheck, Workflow, Zap } from 'lucide-react'

export default function Home() {
  return (
    <main className="min-h-screen bg-gradient-to-b from-slate-50 via-white to-slate-100 dark:from-slate-950 dark:via-slate-900 dark:to-slate-950">
      <div className="container mx-auto px-4 py-16">
        <div className="text-center mb-16">
          <span className="inline-flex items-center gap-2 rounded-full bg-blue-100 px-4 py-1 text-sm font-semibold text-blue-700 dark:bg-blue-900/30 dark:text-blue-300">
            BuildGuard · DevSecOps Risk Prediction Platform
          </span>
          <h1 className="mt-6 text-5xl font-bold leading-tight text-slate-900 dark:text-white">
            Giám sát CI/CD và dự báo rủi ro builds trong một dashboard
          </h1>
          <p className="mt-4 text-xl text-gray-600 dark:text-gray-300 max-w-3xl mx-auto">
            BuildGuard kết nối với GitHub thông qua OAuth đọc-only, thu thập dữ liệu workflow runs, commits,
            phân tích chất lượng code và bảo mật trước khi mô hình Bayesian CNN đưa ra dự đoán rủi ro.
          </p>
        </div>

        <div className="text-center space-x-4">
          <Link href="/dashboard">
            <Button size="lg" className="text-lg px-8">
              Mở Dashboard
            </Button>
          </Link>
          <Link href="/integrations/github">
            <Button size="lg" variant="outline" className="text-lg px-8">
              Kết nối GitHub OAuth
            </Button>
          </Link>
        </div>

        <div className="mt-16 grid md:grid-cols-3 gap-6">
          <Card className="border border-blue-100 shadow-sm dark:border-blue-900/40">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Workflow className="h-5 w-5 text-blue-600" />
                Thu thập dữ liệu CI/CD
              </CardTitle>
              <CardDescription>
                Đồng bộ commits, workflow runs và artifacts từ GitHub Actions
              </CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-gray-600 dark:text-gray-400">
                OAuth đọc-only, không cần GitHub App · hỗ trợ mở rộng sang các nền tảng CI khác.
              </p>
            </CardContent>
          </Card>

          <Card className="border border-emerald-100 shadow-sm dark:border-emerald-900/40">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <ShieldCheck className="h-5 w-5 text-emerald-600" />
                Phân tích chất lượng & bảo mật
              </CardTitle>
              <CardDescription>
                Tích hợp SonarQube và các chỉ số quality gate
              </CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-gray-600 dark:text-gray-400">
                Theo dõi bugs, coverage, technical debt và vulnerabilities cho từng build.
              </p>
            </CardContent>
          </Card>

          <Card className="border border-purple-100 shadow-sm dark:border-purple-900/40">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Zap className="h-5 w-5 text-purple-600" />
                Bayesian Risk Engine
              </CardTitle>
              <CardDescription>
                Mô hình Bayesian CNN dự đoán rủi ro và độ bất định
              </CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-gray-600 dark:text-gray-400">
                Prototype hiện giả lập dữ liệu · dễ dàng tích hợp mô hình thực tế sau khi huấn luyện.
              </p>
            </CardContent>
          </Card>
        </div>

        <div className="mt-16 border-t pt-12">
          <div className="grid md:grid-cols-2 gap-8">
            <div>
              <h3 className="text-lg font-semibold mb-3">Tính năng chính</h3>
              <ul className="space-y-2 text-gray-600 dark:text-gray-400">
                <li>✓ GitHub OAuth đọc-only · không yêu cầu quyền ghi hoặc secret.</li>
                <li>✓ Đa nguồn dữ liệu: workflow runs, commits diff, logs, artifacts.</li>
                <li>✓ Bảo mật & chất lượng: SonarQube metrics kết hợp đánh giá rủi ro ML.</li>
                <li>✓ Dashboard trực quan: biểu đồ xu hướng, heatmap, chi tiết từng build.</li>
                <li>✓ Sẵn sàng tích hợp AI: pipeline dữ liệu chuẩn cho Bayesian CNN.</li>
              </ul>
            </div>
            <div>
              <h3 className="text-lg font-semibold mb-3">Công nghệ</h3>
              <ul className="space-y-2 text-gray-600 dark:text-gray-400">
                <li>
                  <Github className="mr-2 inline h-4 w-4" />
                  GitHub REST API với scopes: read:user, repo, read:org, workflow.
                </li>
                <li>🎨 Frontend: Next.js 14, Tailwind, shadcn/ui, Recharts.</li>
                <li>⚙️ Backend (prototype): FastAPI, background worker, MongoDB.</li>
                <li>🧠 ML: Bayesian CNN (tích hợp sau) + pipeline features chuẩn hóa.</li>
                <li>🐳 DevOps: Docker Compose, GitHub Actions cho CI, bảo mật hạ tầng.</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </main>
  )
}
