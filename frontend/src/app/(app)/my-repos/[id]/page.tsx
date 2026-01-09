"use client";

import { redirect, useParams } from "next/navigation";

export default function RepoRedirectPage() {
    const params = useParams();
    redirect(`/my-repos/${params.id}/overview`);
}
