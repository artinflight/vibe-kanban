// Config metadata adapter for VK's restricted classification client only.
// It preserves native safety values; normal agents and thread/turn events pass
// through untouched. The current backend consumes only these two config fields.
export function classifierInvocation(args) {
  const overrides = new Map();
  for (let i = 0; i < args.length - 1; i++) {
    if (args[i] === '-c') {
      const value = args[++i];
      const separator = value.indexOf('=');
      if (separator > 0) {
        overrides.set(value.slice(0, separator), value.slice(separator + 1));
      }
    }
  }
  return (
    args[0] === 'app-server' &&
    [
      'project_doc_max_bytes=0',
      'skills.include_instructions=false',
      'features.skip_host_skill_discovery=true',
      'features.shell_tool=false',
      'features.multi_agent=false',
      'features.hooks=false',
      'features.plugins=false',
    ].every((flag) => {
      const [key, value] = flag.split('=');
      return overrides.get(key) === value;
    })
  );
}

export function compactClassifierConfig(message, classifier) {
  if (!classifier || !message?.result?.config) return message;
  const config = message.result.config;
  if (typeof config !== 'object' || Array.isArray(config)) return message;
  // Never manufacture false flags or empty MCP maps. Missing/unsafe native
  // values still reach the existing backend guard and fail closed.
  message.result.config = {
    features: config.features,
    mcp_servers: config.mcp_servers,
  };
  return message;
}
