import { DotSidechatLive } from './DotSidechatLive';
import { DotSidechatFixture } from './DotSidechatFixture';

export function DotSidechat({ workspaceId }: { workspaceId?: string }) {
  return import.meta.env.VITE_DOT_SIDECHAT === '1' ? (
    <DotSidechatLive key={workspaceId ?? 'none'} workspaceId={workspaceId} />
  ) : (
    <DotSidechatFixture key={workspaceId ?? 'none'} />
  );
}
