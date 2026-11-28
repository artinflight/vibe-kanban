export const calls: Array<{ id: string; response: unknown }> = [];
export const approvalsApi = {
  async respond(id: string, response: unknown) {
    calls.push({ id, response });
    return response;
  },
};
