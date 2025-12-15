'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { ExternalLink } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'

export function GitHubTokensTab() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>GitHub API Tokens</CardTitle>
        <CardDescription>
          Manage GitHub personal access tokens for API rate limits
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          <p className="text-sm text-muted-foreground">
            GitHub tokens are used to increase API rate limits for data collection.
            The application uses a token pool to distribute requests across multiple tokens.
          </p>
          <Link href="/admin/settings/tokens">
            <Button>
              Manage Tokens
              <ExternalLink className="ml-2 h-4 w-4" />
            </Button>
          </Link>
        </div>
      </CardContent>
    </Card>
  )
}
