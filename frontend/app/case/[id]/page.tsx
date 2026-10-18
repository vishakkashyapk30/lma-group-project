// `/case/[id]` Case workspace: stage rail + three panes (plan §13.5), inside the workspace provider.
import { WorkspaceShellLazy } from "@/components/workspace/WorkspaceShellLazy";
import { WorkspaceProvider } from "@/lib/workspace";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <WorkspaceProvider caseId={id}>
      <WorkspaceShellLazy caseId={id} />
    </WorkspaceProvider>
  );
}
