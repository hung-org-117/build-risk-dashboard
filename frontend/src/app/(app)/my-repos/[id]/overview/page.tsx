"use client";

import { useRepo } from "@/components/repositories/RepoContext";
import { OverviewTab } from "@/components/repositories/tabs/OverviewTab";

export default function OverviewPage() {
    const {
        repo,
        progress,
        builds,
    } = useRepo();

    if (!repo) return null;

    return (
        <OverviewTab
            repo={repo}
            progress={progress}
            builds={builds}
        />
    );
}
