"use client";

import { Input } from "@/components/ui/input";
import { useDebounce } from "@/hooks/use-debounce";
import {
  CheckCircle2,
  Loader2,
  Plus,
  Trash2,
} from "lucide-react";
import {
  useCallback,
  useEffect,
  useState
} from "react";

import { useRouter } from "next/navigation";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { DataTable, type DataTableColumn } from "@/components/ui/data-table";
import { toast } from "@/components/ui/use-toast";
import { useSSE } from "@/contexts/sse-context";
import { reposApi } from "@/lib/api";
import { formatDateTime } from "@/lib/utils";
import type {
  RepositoryRecord
} from "@/types";
import { ImportProgressDisplay } from "@/components/repositories/ImportProgressDisplay";


const PAGE_SIZE = 20;

export default function AdminReposPage() {
  const router = useRouter();
  const [repositories, setRepositories] = useState<RepositoryRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [tableLoading, setTableLoading] = useState(false);


  // Search state
  const [searchQuery, setSearchQuery] = useState("");
  const debouncedSearchQuery = useDebounce(searchQuery, 500);

  // Status filter state
  const [statusFilter, setStatusFilter] = useState<string>("");

  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [feedback, setFeedback] = useState<string | null>(null);

  const { subscribe } = useSSE();

  const loadRepositories = useCallback(
    async (pageNumber = 1, withSpinner = false) => {
      if (withSpinner) {
        setTableLoading(true);
      }
      try {
        const data = await reposApi.list({
          skip: (pageNumber - 1) * PAGE_SIZE,
          limit: PAGE_SIZE,
          q: debouncedSearchQuery || undefined,
          status: statusFilter || undefined,
        });
        setRepositories(data.items);
        setTotal(data.total);
        setPage(pageNumber);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
        setTableLoading(false);
      }
    },
    [debouncedSearchQuery, statusFilter]
  );

  // WebSocket connection
  useEffect(() => {
    const unsubscribe = subscribe("REPO_UPDATE", (data: any) => {
      setRepositories((prev) => {
        return prev.map((repo) => {
          if (repo.id === data.repo_id) {
            // Update status and stats if available
            return {
              ...repo,
              status: data.status,
              ...(data.stats || {}),
            };
          }
          return repo;
        });
      });

      if (data.status === "imported" || data.status === "failed") {
        // Reload to get fresh data (stats, etc)
        loadRepositories(page);
      }
    });

    return () => {
      unsubscribe();
    };
  }, [subscribe, loadRepositories, page]);

  useEffect(() => {
    loadRepositories(1, true);
  }, [loadRepositories]);



  const [deleteLoading, setDeleteLoading] = useState<Record<string, boolean>>({});

  const handleDelete = async (repo: RepositoryRecord) => {
    if (deleteLoading[repo.id]) return;

    // Confirmation dialog
    const confirmed = window.confirm(
      `Are you sure you want to delete "${repo.full_name}"?\n\nThis will permanently delete the repository configuration and all associated build data.`
    );
    if (!confirmed) return;

    setDeleteLoading((prev) => ({ ...prev, [repo.id]: true }));
    try {
      await reposApi.delete(repo.id);
      toast({ title: "Deleted", description: `Repository "${repo.full_name}" deleted.` });
      loadRepositories(page);
    } catch (err) {
      console.error(err);
    } finally {
      setDeleteLoading((prev) => ({ ...prev, [repo.id]: false }));
    }
  };

  const getRepoStatusBadge = (status: string) => {
    switch (status) {
      case "queued":
        return <Badge variant="secondary">Queued</Badge>;
      case "fetching":
        return <Badge variant="default" className="bg-cyan-500 hover:bg-cyan-600"><Loader2 className="w-3 h-3 mr-1 animate-spin" /> Fetching</Badge>;
      case "ingesting":
        return <Badge variant="default" className="bg-blue-500 hover:bg-blue-600"><Loader2 className="w-3 h-3 mr-1 animate-spin" /> Ingesting</Badge>;
      case "ingestion_complete":
        return <Badge variant="default" className="bg-green-500 hover:bg-green-600"><CheckCircle2 className="w-3 h-3 mr-1" /> Ingested</Badge>;
      case "ingestion_partial":
        return <Badge variant="default" className="bg-amber-500 hover:bg-amber-600">Ingestion Partial</Badge>;
      case "processing":
        return <Badge variant="default" className="bg-purple-500 hover:bg-purple-600"><Loader2 className="w-3 h-3 mr-1 animate-spin" /> Processing</Badge>;
      case "partial":
        return <Badge variant="default" className="bg-amber-500 hover:bg-amber-600">Partial</Badge>;
      case "failed":
        return <Badge variant="destructive">Failed</Badge>;
      default:
        return <Badge variant="outline" className="border-green-500 text-green-600">Imported</Badge>;
    }
  };

  const columns: DataTableColumn<RepositoryRecord>[] = [
    {
      key: "full_name",
      header: "Repo name",
      render: (repo) => <span className="font-medium text-foreground">{repo.full_name}</span>,
    },
    {
      key: "status",
      header: "Import Status",
      render: (repo) => getRepoStatusBadge(repo.status),
    },
    {
      key: "last_synced_at",
      header: "Last sync time",
      render: (repo) => <span className="text-muted-foreground">{formatDateTime(repo.last_synced_at)}</span>,
    },
    {
      key: "progress",
      header: "Builds Progress",
      render: (repo) => (
        <ImportProgressDisplay
          repoId={repo.id}
          totalFetched={repo.builds_fetched}
          totalIngested={repo.builds_ingested}
          totalProcessed={repo.builds_completed}
          totalFailed={repo.builds_ingestion_failed + repo.builds_processing_failed}
          importStatus={repo.status}
        />
      ),
    },
  ];

  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle>Loading repositories...</CardTitle>
            <CardDescription>Fetching tracked repositories.</CardDescription>
          </CardHeader>
          <CardContent>
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="flex flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <CardTitle>Repository & Data Management</CardTitle>
            <CardDescription>
              Connect GitHub repositories and ingest builds.
            </CardDescription>
          </div>
          <Button onClick={() => router.push("/repositories/import")} className="gap-2 bg-emerald-600 hover:bg-emerald-700">
            <Plus className="h-4 w-4" /> Add GitHub Repository
          </Button>
        </CardHeader>
      </Card>

      {feedback ? (
        <div className="rounded-lg border border-blue-200 bg-blue-50/60 p-3 text-sm text-blue-700 dark:border-blue-800 dark:bg-blue-900/20 dark:text-blue-200">
          {feedback}
        </div>
      ) : null}

      <Card>
        <CardHeader className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <CardTitle>Connected repositories</CardTitle>
            <CardDescription>
              Overview of every repository currently tracked by BuildGuard
            </CardDescription>
          </div>
          <div className="flex items-center gap-2">
            <div className="relative w-64">
              <Input
                placeholder="Search repositories..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="h-9"
              />
            </div>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="h-9 rounded-md border border-input bg-background px-3 py-1 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
            >
              <option value="">All Status</option>
              <option value="queued">Queued</option>
              <option value="fetching">Fetching</option>
              <option value="ingesting">Ingesting</option>
              <option value="ingested">Ingested</option>
              <option value="processing">Processing</option>
              <option value="processed">Processed</option>
              <option value="failed">Failed</option>
            </select>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          <DataTable
            columns={columns}
            data={repositories}
            total={total}
            page={page}
            pageSize={PAGE_SIZE}
            loading={tableLoading}
            emptyMessage="No repositories have been connected yet."
            itemName="repositories"
            onPageChange={(p) => loadRepositories(p, true)}
            onRowClick={(repo) => router.push(`/repositories/${repo.id}`)}
            rowKey={(repo) => repo.id}
            alwaysShowPagination={true}
            actions={(repo) => (
              <Button
                size="icon"
                variant="ghost"
                className="h-8 w-8 text-red-500 hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-900/20"
                onClick={(e) => {
                  e.stopPropagation();
                  handleDelete(repo);
                }}
                disabled={deleteLoading[repo.id]}
                title="Delete Repository"
              >
                {deleteLoading[repo.id] ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Trash2 className="h-4 w-4" />
                )}
                <span className="sr-only">Delete</span>
              </Button>
            )}
          />
        </CardContent>
      </Card>
    </div>
  );
}
