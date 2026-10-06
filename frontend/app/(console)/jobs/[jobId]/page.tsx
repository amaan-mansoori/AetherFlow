import type { Metadata } from "next";
import { JobDetailClient } from "@/components/jobs/job-detail";

export const metadata: Metadata = { title: "Job execution" };

export default async function JobPage({ params }: { params: Promise<{ jobId: string }> }) {
  const { jobId } = await params;
  return <JobDetailClient jobId={jobId} />;
}
