// Route stub: `/case/[id]` Case workspace: stage rail + three panes (plan §13.5).
import { WorkspaceShell } from "@/components/workspace/WorkspaceShell";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <WorkspaceShell caseId={id} />;
}
