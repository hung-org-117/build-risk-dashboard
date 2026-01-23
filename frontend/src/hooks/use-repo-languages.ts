import { useState, useEffect, useRef } from "react";
import { reposApi } from "@/lib/api/repos";

export function useRepoLanguages(repos: Array<{ id: string; full_name: string }>) {
    const [repoLanguages, setRepoLanguages] = useState<Record<string, string[]>>({});
    const [loading, setLoading] = useState(false);

    // Track processed repos key to avoid redundant calls but allow updates
    const processedReposRef = useRef<string>("");

    useEffect(() => {
        if (repos.length === 0) return;

        // Create a key based on repo full names to detect content changes
        const currentReposKey = JSON.stringify(repos.map(r => r.full_name).sort());
        if (currentReposKey === processedReposRef.current) return;

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
                processedReposRef.current = currentReposKey;
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
    }, [repos]); // Dependency on repos ensures we check whenever reference changes

    return { repoLanguages, loading };
}
