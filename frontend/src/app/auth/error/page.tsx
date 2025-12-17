"use client";

import { useSearchParams, useRouter } from "next/navigation";
import { Suspense } from "react";
import { ShieldX, ArrowLeft, AlertTriangle, XCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";

function AuthErrorContent() {
    const searchParams = useSearchParams();
    const router = useRouter();

    const errorCode = searchParams.get("code") || "unknown";
    const errorMessage = searchParams.get("message") || "An unexpected error occurred during authentication.";

    // Determine error type and styling based on error code
    const is403 = errorCode === "403";
    const is400 = errorCode === "400";
    const is500 = errorCode === "500";

    const getErrorTitle = () => {
        if (is403) return "Access Denied";
        if (is400) return "Authentication Failed";
        if (is500) return "Server Error";
        return "Authentication Error";
    };

    const getErrorIcon = () => {
        if (is403) return <ShieldX className="h-16 w-16 text-destructive" />;
        if (is500) return <AlertTriangle className="h-16 w-16 text-amber-500" />;
        return <XCircle className="h-16 w-16 text-destructive" />;
    };

    const getErrorDescription = () => {
        if (is403) {
            return "You don't have permission to access this application. Please contact your organization administrator for access.";
        }
        if (is400) {
            return "The authentication request was invalid or has expired. Please try logging in again.";
        }
        if (is500) {
            return "Something went wrong on our end. Please try again later or contact support.";
        }
        return "An error occurred during the authentication process.";
    };

    const handleTryAgain = () => {
        // Use window.location to force a full navigation (bypass any cached auth state)
        window.location.href = "/login";
    };

    const handleGoHome = () => {
        window.location.href = "/";
    };

    return (
        <main className="min-h-screen flex items-center justify-center bg-background p-4">
            <Card className="w-full max-w-lg">
                <CardHeader className="text-center pb-2">
                    <div className="flex justify-center mb-4">
                        {getErrorIcon()}
                    </div>
                    <CardTitle className="text-2xl font-bold">
                        {getErrorTitle()}
                    </CardTitle>
                    <CardDescription className="text-base">
                        {getErrorDescription()}
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                    {/* Error Details Box */}
                    <div className="rounded-lg bg-muted/50 border p-4">
                        <div className="flex items-center gap-2 text-sm text-muted-foreground mb-2">
                            <span className="font-medium">Error Details</span>
                            <span className="px-2 py-0.5 rounded bg-secondary text-secondary-foreground text-xs">
                                Code: {errorCode}
                            </span>
                        </div>
                        <p className="text-sm break-words">
                            {decodeURIComponent(errorMessage)}
                        </p>
                    </div>

                    {/* Actions */}
                    <div className="flex flex-col gap-3">
                        <Button
                            variant="default"
                            className="w-full"
                            onClick={handleTryAgain}
                        >
                            Try Again
                        </Button>
                        <Button
                            variant="outline"
                            className="w-full gap-2"
                            onClick={handleGoHome}
                        >
                            <ArrowLeft className="h-4 w-4" />
                            Back to Home
                        </Button>
                    </div>

                    {/* Help Section */}
                    {is403 && (
                        <div className="text-center pt-4 border-t">
                            <p className="text-sm text-muted-foreground">
                                Need access?{" "}
                                <a
                                    href="mailto:admin@example.com"
                                    className="text-primary hover:underline"
                                >
                                    Contact your administrator
                                </a>
                            </p>
                        </div>
                    )}
                </CardContent>
            </Card>
        </main>
    );
}

export default function AuthErrorPage() {
    return (
        <Suspense
            fallback={
                <main className="min-h-screen flex items-center justify-center bg-background">
                    <div className="animate-pulse text-muted-foreground">Loading...</div>
                </main>
            }
        >
            <AuthErrorContent />
        </Suspense>
    );
}
