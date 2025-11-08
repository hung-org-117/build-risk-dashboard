import { notFound } from 'next/navigation'

import { buildApi } from '@/lib/api'
import type { BuildDetail } from '@/types'
import { BuildDetailClient } from './view'

interface BuildDetailPageProps {
  params: { id: string }
}

async function fetchBuildDetail(id: number): Promise<BuildDetail | null> {
  try {
    const build = await buildApi.getById(id)
    return build
  } catch (error) {
    console.error('Failed to load build detail', error)
    return null
  }
}

export default async function BuildDetailPage({ params }: BuildDetailPageProps) {
  const id = Number(params.id)
  if (Number.isNaN(id)) {
    notFound()
  }

  const build = await fetchBuildDetail(id)

  if (!build) {
    notFound()
  }

  return <BuildDetailClient build={build} />
}
