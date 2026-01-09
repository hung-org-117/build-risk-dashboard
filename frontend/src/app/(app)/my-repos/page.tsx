"use client";

import { Input } from "@/components/ui/input";
import { useDebounce } from "@/hooks/use-debounce";
import { CheckCircle2, Loader2, Search } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { Badge } from "@/components/ui/badge";
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { reposApi } from "@/lib/api";
import { formatDateTime } from "@/lib/utils";
import type { RepositoryRecord } from "@/types";
import { useWebSocket } from "@/contexts/websocket-context";
import { ImportProgressDisplay } from "@/components/repositories/ImportProgressDisplay";

const PAGE_SIZE = 20;

export default function UserReposPage() {
    const router = useRouter();
    const { subscribe } = useWebSocket();

    const [repositories, setRepositories] = useState<RepositoryRecord[]>([]);
    const [loading, setLoading] = useState(true);
    const [tableLoading, setTableLoading] = useState(false);

    const [searchQuery, setSearchQuery] = useState("");
    const debouncedSearchQuery = useDebounce(searchQuery, 500);
    const [statusFilter, setStatusFilter] = useState<string>("");

    const [page, setPage] = useState(1);
    const [total, setTotal] = useState(0);

    const loadRepositories = useCallback(
        async (pageNumber = 1, withSpinner = false) => {
            if (withSpinner) setTableLoading(true);
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

    // WebSocket subscription for real-time updates
    useEffect(() => {
        const unsubscribe = subscribe("REPO_UPDATE", (data: any) => {
            setRepositories((prev) => {
                let found = false;
                const next = prev.map((repo) => {
                    if (repo.id === data.repo_id) {
                        found = true;
                        return {
                            ...repo,
                            status: data.status,
                            ...(data.stats || {}),
                        };
                    }
                    return repo;
                });

                // If the updated repo is not in the current list (e.g. newly imported), 
                // we might want to reload to show it, but for pagination simplicity
                // we'll stick to updating existing ones or reloading if critical.
                return next;
            });

            // Create a reload trigger if status changes significantly
            if (data.status === "imported" || data.status === "failed") {
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

    const totalPages = total > 0 ? Math.ceil(total / PAGE_SIZE) : 1;
    const pageStart = total === 0 ? 0 : (page - 1) * PAGE_SIZE + 1;
    const pageEnd = total === 0 ? 0 : Math.min(page * PAGE_SIZE, total);

    const handlePageChange = (direction: "prev" | "next") => {
        const targetPage =
            direction === "prev"
                ? Math.max(1, page - 1)
                : Math.min(totalPages, page + 1);
        if (targetPage !== page) {
            void loadRepositories(targetPage, true);
        }
    };

    if (loading) {
        return (
            <div className="flex min-h-[60vh] items-center justify-center">
                <Card className="w-full max-w-md">
                    <CardHeader>
                        <CardTitle>Loading repositories...</CardTitle>
                        <CardDescription>Fetching your repositories.</CardDescription>
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
                <CardHeader className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                    <div>
                        <CardTitle>My Repositories</CardTitle>
                        <CardDescription>
                            Repositories you have access to.
                        </CardDescription>
                    </div>
                    <div className="flex items-center gap-2">
                        <div className="relative w-64">
                            <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                            <Input
                                placeholder="Search repositories..."
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                                className="pl-8 h-9"
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
                    <div className="overflow-x-auto">
                        <table className="min-w-full divide-y divide-slate-200 text-sm dark:divide-slate-800">
                            <thead className="bg-slate-50 dark:bg-slate-900/40">
                                <tr>
                                    <th className="px-6 py-3 text-left font-semibold text-slate-500">
                                        Repository
                                    </th>
                                    <th className="px-6 py-3 text-left font-semibold text-slate-500">
                                        Status
                                    </th>
                                    <th className="px-6 py-3 text-left font-semibold text-slate-500">
                                        Last Sync
                                    </th>
                                    <th className="px-6 py-3 text-left font-semibold text-slate-500">
                                        Builds Progress
                                    </th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                                {repositories.length === 0 ? (
                                    <tr>
                                        <td
                                            colSpan={4}
                                            className="px-6 py-8 text-center text-sm text-muted-foreground"
                                        >
                                            No repositories found.
                                        </td>
                                    </tr>
                                ) : (
                                    repositories.map((repo) => (
                                        <tr
                                            key={repo.id}
                                            className="cursor-pointer transition hover:bg-slate-50 dark:hover:bg-slate-900/40"
                                            onClick={() => router.push(`/my-repos/${repo.id}`)}
                                        >
                                            <td className="px-6 py-4 font-medium text-foreground">
                                                {repo.full_name}
                                            </td>
                                            <td className="px-6 py-4">
                                                {repo.status === "queued" ? (
                                                    <Badge variant="secondary">Queued</Badge>
                                                ) : repo.status === "fetching" ? (
                                                    <Badge variant="default" className="bg-cyan-500 hover:bg-cyan-600"><Loader2 className="w-3 h-3 mr-1 animate-spin" /> Fetching</Badge>
                                                ) : repo.status === "ingesting" ? (
                                                    <Badge variant="default" className="bg-blue-500 hover:bg-blue-600"><Loader2 className="w-3 h-3 mr-1 animate-spin" /> Ingesting</Badge>
                                                ) : ["ingested", "ingestion_complete"].includes(repo.status) ? (
                                                    <Badge variant="default" className="bg-green-500 hover:bg-green-600"><CheckCircle2 className="w-3 h-3 mr-1" /> Ingested</Badge>
                                                ) : repo.status === "ingestion_partial" ? (
                                                    <Badge variant="default" className="bg-amber-500 hover:bg-amber-600">Ingestion Partial</Badge>
                                                ) : repo.status === "processing" ? (
                                                    <Badge variant="default" className="bg-purple-500 hover:bg-purple-600"><Loader2 className="w-3 h-3 mr-1 animate-spin" /> Processing</Badge>
                                                ) : repo.status === "partial" ? (
                                                    <Badge variant="default" className="bg-amber-500 hover:bg-amber-600">Partial</Badge>
                                                ) : repo.status === "failed" ? (
                                                    <Badge variant="destructive">Failed</Badge>
                                                ) : (
                                                    <Badge variant="outline" className="border-green-500 text-green-600">Imported</Badge>
                                                )}
                                            </td>
                                            <td className="px-6 py-4 text-muted-foreground">
                                                {formatDateTime(repo.last_synced_at)}
                                            </td>
                                            <td className="px-6 py-4">
                                                <ImportProgressDisplay
                                                    repoId={repo.id}
                                                    totalFetched={repo.builds_fetched}
                                                    totalIngested={repo.builds_ingested}
                                                    totalProcessed={repo.builds_completed}
                                                    totalFailed={repo.builds_ingestion_failed + repo.builds_processing_failed}
                                                    importStatus={repo.status}
                                                />
                                            </td>
                                        </tr>
                                    ))
                                )}
                            </tbody>
                        </table>
                    </div>
                    <div className="flex items-center justify-between border-t border-slate-200 px-6 py-4 text-sm text-muted-foreground dark:border-slate-800">
                        <div>
                            {total > 0
                                ? `Showing ${pageStart}-${pageEnd} of ${total} repositories`
                                : "No repositories to display"}
                        </div>
                        <div className="flex items-center gap-2">
                            {tableLoading && (
                                <Loader2 className="h-4 w-4 animate-spin" />
                            )}
                            <Button
                                size="sm"
                                variant="outline"
                                onClick={() => handlePageChange("prev")}
                                disabled={page === 1 || tableLoading}
                            >
                                Previous
                            </Button>
                            <span className="text-xs">
                                Page {page} of {totalPages}
                            </span>
                            <Button
                                size="sm"
                                variant="outline"
                                onClick={() => handlePageChange("next")}
                                disabled={page >= totalPages || tableLoading}
                            >
                                Next
                            </Button>
                        </div>
                    </div>
                </CardContent>
            </Card>
        </div>
    );
}
