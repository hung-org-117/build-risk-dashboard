"use client";

import { useEffect, useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Loader2, AlertCircle } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { integrationApi } from "@/lib/api";
import { useAuth } from "@/contexts/auth-context";

function LoginContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { authenticated, loading: authLoading, error: authError } = useAuth();
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Read error from URL query params (from OAuth callback failure)
  const urlError = searchParams.get("error");

  useEffect(() => {
    if (authLoading) {
      return;
    }
    if (authenticated) {
      router.replace("/overview");
    }
  }, [authenticated, authLoading, router]);

  const handleLogin = async () => {
    setError(null);
    setActionLoading(true);
    try {
      const { authorize_url } = await integrationApi.startGithubOAuth("/");
      window.location.href = authorize_url;
    } catch (err) {
      console.error(err);
      setError("Unable to initiate GitHub OAuth. Check configuration.");
    } finally {
      setActionLoading(false);
    }
  };

  const handleGoogleLogin = async () => {
    setError(null);
    setActionLoading(true);
    try {
      const { authorize_url } = await integrationApi.startGoogleOAuth();
      window.location.href = authorize_url;
    } catch (err) {
      console.error(err);
      setError("Unable to initiate Google OAuth. Check configuration.");
    } finally {
      setActionLoading(false);
    }
  };

  const combinedError = urlError ? decodeURIComponent(urlError) : (error ?? authError);

  return (
    <main className="min-h-screen flex items-center justify-center bg-slate-50 dark:bg-slate-900">
      <Card className="w-full max-w-lg border-slate-200 dark:border-slate-800 shadow-xl">
        <CardHeader className="flex flex-col items-center text-center space-y-2">
          <div className="rounded-full bg-blue-100 p-3 mb-2 dark:bg-blue-900/30">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="h-8 w-8 text-blue-600 dark:text-blue-400"
            >
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10" />
            </svg>
          </div>
          <CardTitle className="text-2xl font-bold">Welcome back</CardTitle>
          <CardDescription className="text-base">
            Sign in to BuildRisk Dashboard to verify data integrity.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col items-center justify-center p-8 pt-4">
          <div className="flex flex-col items-center justify-center space-y-6 w-full">
            {combinedError ? (
              <div className="w-full rounded-md bg-destructive/10 p-4 text-sm text-destructive flex gap-3 items-start border border-destructive/20">
                <AlertCircle className="h-5 w-5 shrink-0 mt-0.5" />
                <div className="space-y-1">
                  <p className="font-semibold">Authentication Error</p>
                  <p>{combinedError}</p>
                </div>
              </div>
            ) : null}

            <div className="flex items-center justify-center w-full">
              <Button
                onClick={handleLogin}
                size="lg"
                className="w-full h-11 text-base font-medium"
                disabled={authLoading || actionLoading}
              >
                {actionLoading || authLoading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    {actionLoading ? "Connecting to GitHub..." : "Checking session..."}
                  </>
                ) : (
                  <div className="flex items-center justify-center gap-2">
                    <svg className="h-5 w-5" viewBox="0 0 24 24" fill="currentColor">
                      <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z" />
                    </svg>
                    Continue with GitHub
                  </div>
                )}
              </Button>
            </div>

            <div className="relative w-full">
              <div className="absolute inset-0 flex items-center">
                <span className="w-full border-t border-slate-200 dark:border-slate-700" />
              </div>
              <div className="relative flex justify-center text-xs uppercase">
                <span className="bg-white dark:bg-slate-900 px-2 text-muted-foreground">Guest Access</span>
              </div>
            </div>

            <div className="flex items-center justify-center w-full">
              <Button
                variant="outline"
                onClick={handleGoogleLogin}
                size="lg"
                className="w-full h-11 text-base font-medium"
                disabled={authLoading || actionLoading}
              >
                <div className="flex items-center justify-center gap-2">
                  <svg className="h-5 w-5" viewBox="0 0 24 24">
                    <path
                      d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                      fill="#4285F4"
                    />
                    <path
                      d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                      fill="#34A853"
                    />
                    <path
                      d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                      fill="#FBBC05"
                    />
                    <path
                      d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                      fill="#EA4335"
                    />
                  </svg>
                  Sign in with Google
                </div>
              </Button>
            </div>
            <p className="text-xs text-muted-foreground text-center px-4">
              By continuing, you agree to our Terms of Service and Privacy Policy.
              Access is restricted to authorized organization members only.
            </p>
          </div>
        </CardContent>
      </Card>
    </main>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center bg-slate-50 dark:bg-slate-900">
        <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
      </div>
    }>
      <LoginContent />
    </Suspense>
  );
}
