export const state = { checkpoints: [] as {execution_process_id:string;observation_state:string}[], fail: false, calls: [] as string[] };
export async function makeLocalApiRequest(path: string) {
  state.calls.push(path);
  return new Response(JSON.stringify({success: !state.fail, data: {checkpoints: state.checkpoints}}), {status: state.fail ? 503 : 200});
}
export async function handleApiResponse<T>(response: Response): Promise<T> {
  if (!response.ok) throw new Error('status unavailable');
  return (await response.json()).data;
}
