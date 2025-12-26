"use client";

import { useState, useEffect } from "react";
import { featuresApi } from "@/lib/api";

interface CIProviderOption {
    value: string;
    label: string;
}

interface FeaturesConfig {
    languages: string[];
    frameworks: string[];
    frameworksByLanguage: Record<string, string[]>;
    ciProviders: CIProviderOption[];
}

interface UseFeaturesConfigReturn {
    config: FeaturesConfig | null;
    isLoading: boolean;
    error: string | null;
}

/**
 * Hook to fetch feature configuration from the API.
 * Returns languages, frameworks, and CI providers for UI selection.
 */
export function useFeaturesConfig(): UseFeaturesConfigReturn {
    const [config, setConfig] = useState<FeaturesConfig | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const fetchConfig = async () => {
            try {
                setIsLoading(true);
                const response = await featuresApi.getConfig();
                console.log("Features config:", response);
                setConfig({
                    languages: response.languages,
                    frameworks: response.frameworks,
                    frameworksByLanguage: response.frameworks_by_language,
                    ciProviders: response.ci_providers,
                });
                setError(null);
            } catch (err) {
                console.error("Failed to fetch features config:", err);
                setError("Failed to load configuration");
                // Fallback to defaults
                setConfig({
                    languages: ["python", "javascript", "java", "go", "ruby"],
                    frameworks: ["pytest", "jest", "junit"],
                    frameworksByLanguage: {},
                    ciProviders: [
                        { value: "github_actions", label: "GitHub Actions" },
                        { value: "travis_ci", label: "Travis CI" },
                        { value: "circleci", label: "CircleCI" },
                        { value: "gitlab_ci", label: "GitLab CI" },
                    ],
                });
            } finally {
                setIsLoading(false);
            }
        };

        fetchConfig();
    }, []);

    return { config, isLoading, error };
}
