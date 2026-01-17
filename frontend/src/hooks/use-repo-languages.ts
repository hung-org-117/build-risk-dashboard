import { useState, useEffect } from "react";
import { reposApi } from "@/lib/api/repos";

export function useRepoLanguages(repos: Array<{ id: string; full_name: string }>) {
    const [repoLanguages, setRepoLanguages] = useState<Record<string, string[]>>({});
    const [loading, setLoading] = useState(false);
    const [fetched, setFetched] = useState(false);

    useEffect(() => {
        if (repos.length === 0 || fetched) return;

        const detectLanguagesBatch = async () => {
            setLoading(true);
            try {
                // Get list of full names
                const fullNames = repos.map(r => r.full_name);

                // Call batch API
                const results = await reposApi.detectLanguagesBatch(fullNames);

                // Map results back to repo IDs
                const languagesByRepoId: Record<string, string[]> = {};
                repos.forEach(repo => {
                    if (results[repo.full_name]) {
                        languagesByRepoId[repo.id] = results[repo.full_name].map((l: string) => l.toLowerCase());
                    } else {
                        languagesByRepoId[repo.id] = [];
                    }
                });

                setRepoLanguages(languagesByRepoId);
                setFetched(true);
            } catch (err) {
                console.error("Failed to batch detect languages:", err);
                // On error, set empty languages
                setRepoLanguages({});
            } finally {
                setLoading(false);
            }
        };

        detectLanguagesBatch();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [repos]); // Only re-run if repos array changes reference

    return { repoLanguages, loading };
}
