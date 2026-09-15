# Capacity deployment package

Put the post-PR114 configuration repair in VK staging, so deployment from this
repository carries it into any nominated backend service. Scope is the versioned
MCP profile, rendering/install/check tooling, tests and deployment instructions.
No Rust/executor changes, production restart or edits to VK::Errors 2.
See [VK_CAPACITY_DEPLOYMENT.md](VK_CAPACITY_DEPLOYMENT.md).
