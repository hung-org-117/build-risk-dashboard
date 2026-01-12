"use client";

import * as React from "react";
import { Loader2, CheckCircle2 } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

/**
 * Column definition for DataTable
 */
export interface DataTableColumn<T> {
    /** Unique key for the column */
    key: string;
    /** Header text */
    header: string;
    /** Render function for cell content */
    render: (item: T) => React.ReactNode;
    /** Optional className for the column header and cells */
    className?: string;
    /** Optional header className override */
    headerClassName?: string;
}

/**
 * Props for the DataTable component
 */
export interface DataTableProps<T> {
    /** Column definitions */
    columns: DataTableColumn<T>[];
    /** Data array to display */
    data: T[];
    /** Total number of items (for pagination) */
    total: number;
    /** Current page number (1-indexed) */
    page: number;
    /** Number of items per page */
    pageSize: number;
    /** Whether the table is currently loading */
    loading?: boolean;
    /** Message to show when there's no data */
    emptyMessage?: string;
    /** Secondary message for empty state */
    emptySubMessage?: string;
    /** Icon to show in empty state */
    emptyIcon?: React.ReactNode;
    /** Name of items being displayed (for pagination text) */
    itemName?: string;
    /** Callback when page changes */
    onPageChange: (page: number) => void;
    /** Optional callback when a row is clicked */
    onRowClick?: (item: T) => void;
    /** Function to get unique key for each row */
    rowKey: (item: T) => string;
    /** Optional actions column renderer */
    actions?: (item: T) => React.ReactNode;
    /** Optional className for the table container */
    className?: string;
    /** Whether to always show pagination (even with 0 items) */
    alwaysShowPagination?: boolean;
}

/**
 * Reusable DataTable component with built-in pagination, loading states, and empty states.
 * 
 * @example
 * ```tsx
 * <DataTable
 *     columns={[
 *         { key: "name", header: "Name", render: (item) => item.name },
 *         { key: "status", header: "Status", render: (item) => <Badge>{item.status}</Badge> },
 *     ]}
 *     data={items}
 *     total={total}
 *     page={page}
 *     pageSize={20}
 *     loading={isLoading}
 *     emptyMessage="No items yet."
 *     itemName="items"
 *     onPageChange={(p) => loadItems(p)}
 *     onRowClick={(item) => router.push(`/items/${item.id}`)}
 *     rowKey={(item) => item.id}
 *     actions={(item) => <Button onClick={() => handleDelete(item)}>Delete</Button>}
 * />
 * ```
 */
export function DataTable<T>({
    columns,
    data,
    total,
    page,
    pageSize,
    loading = false,
    emptyMessage = "No data available.",
    emptySubMessage,
    emptyIcon,
    itemName = "items",
    onPageChange,
    onRowClick,
    rowKey,
    actions,
    className,
    alwaysShowPagination = false,
}: DataTableProps<T>) {
    const totalPages = total > 0 ? Math.ceil(total / pageSize) : 1;
    const pageStart = total === 0 ? 0 : (page - 1) * pageSize + 1;
    const pageEnd = total === 0 ? 0 : Math.min(page * pageSize, total);

    const handlePrevious = () => {
        if (page > 1) {
            onPageChange(page - 1);
        }
    };

    const handleNext = () => {
        if (page < totalPages) {
            onPageChange(page + 1);
        }
    };

    const showPagination = alwaysShowPagination || total > 0;
    const hasActions = !!actions;
    const columnCount = columns.length + (hasActions ? 1 : 0);

    return (
        <div className={cn("overflow-hidden", className)}>
            {/* Table */}
            <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-slate-200 text-sm dark:divide-slate-800">
                    <thead className="bg-slate-50 dark:bg-slate-900/40">
                        <tr>
                            {columns.map((column) => (
                                <th
                                    key={column.key}
                                    className={cn(
                                        "px-6 py-3 text-left font-semibold text-slate-500",
                                        column.headerClassName || column.className
                                    )}
                                >
                                    {column.header}
                                </th>
                            ))}
                            {hasActions && (
                                <th className="px-6 py-3" />
                            )}
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                        {data.length === 0 ? (
                            <tr>
                                <td
                                    colSpan={columnCount}
                                    className="px-6 py-12 text-center text-muted-foreground"
                                >
                                    <div className="flex flex-col items-center gap-3">
                                        {emptyIcon || (
                                            <CheckCircle2 className="h-12 w-12 text-slate-300" />
                                        )}
                                        <p>{emptyMessage}</p>
                                        {emptySubMessage && (
                                            <p className="text-sm">{emptySubMessage}</p>
                                        )}
                                    </div>
                                </td>
                            </tr>
                        ) : (
                            data.map((item) => (
                                <tr
                                    key={rowKey(item)}
                                    className={cn(
                                        "transition hover:bg-slate-50 dark:hover:bg-slate-900/40",
                                        onRowClick && "cursor-pointer"
                                    )}
                                    onClick={() => onRowClick?.(item)}
                                >
                                    {columns.map((column) => (
                                        <td
                                            key={column.key}
                                            className={cn("px-6 py-4", column.className)}
                                        >
                                            {column.render(item)}
                                        </td>
                                    ))}
                                    {hasActions && (
                                        <td
                                            className="px-6 py-4"
                                            onClick={(e) => e.stopPropagation()}
                                        >
                                            {actions(item)}
                                        </td>
                                    )}
                                </tr>
                            ))
                        )}
                    </tbody>
                </table>
            </div>

            {/* Pagination Footer */}
            {showPagination && (
                <div className="flex items-center justify-between border-t border-slate-200 px-6 py-4 text-sm text-muted-foreground dark:border-slate-800">
                    <div>
                        {total > 0
                            ? `Showing ${pageStart}-${pageEnd} of ${total} ${itemName}`
                            : `No ${itemName} to display`}
                    </div>
                    <div className="flex flex-wrap items-center gap-3">
                        {loading && (
                            <div className="flex items-center gap-2">
                                <Loader2 className="h-4 w-4 animate-spin" />
                                <span className="text-xs">Refreshing...</span>
                            </div>
                        )}
                        <div className="flex items-center gap-2">
                            <Button
                                size="sm"
                                variant="outline"
                                onClick={handlePrevious}
                                disabled={page === 1 || loading}
                            >
                                Previous
                            </Button>
                            <span className="text-xs text-muted-foreground">
                                Page {page} of {totalPages}
                            </span>
                            <Button
                                size="sm"
                                variant="outline"
                                onClick={handleNext}
                                disabled={page >= totalPages || loading}
                            >
                                Next
                            </Button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
