# Same approved installer: corrected administrator invocation

The single authorized noninteractive retry stopped with `sudo: a password is required` before installation. Use the existing MCP administrator terminal. No new grant, alternate route, modified installer, or scope expansion is needed.

The exact installer source supports zero-argument `main()`. The command verifies the original no-follow regular file, size and SHA, loads those bytes without the main guard, and explicitly calls its entrypoint. This avoids formatting-dependent double underscores in the bootstrap. It preserves `-I -S -B`, the original payload and the approved plan.

```bash
sudo -- /usr/bin/python3 -I -S -B -c 'import os,stat,hashlib; fd=os.open("/mnt/vk-storage/vk-retirement-preflight-tests/install-two-profile-29af1c33-r1.py",os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK); info=os.fstat(fd); assert stat.S_ISREG(info.st_mode) and info.st_size==124669; data=os.read(fd,2097153); os.close(fd); assert len(data)==124669 and hashlib.sha256(data).hexdigest()=="6d7db4427a7fed2e056ca28ca71057b99a7cc6cb719c74b99a25b7b778c6a6e3"; namespace={"name":"main"}; exec(compile(data,"reviewed-inspection-installer","exec"),namespace); raise SystemExit(namespace["main"]())' --install --approved-plan 29af1c33e029bc1fe9ef9467fd51a03eb586105d
```

Return the final safe JSON output to root. A `done` acknowledgement alone does not authenticate installation. Do not send passwords or credential material. A failure JSON or authentication denial means hold and report; do not retry through another privilege route.

After successful installation, Staging verifies installed identity/hash/policy/grants/anchor, runs both actual automatic read-only acceptances, and integrates the reviewed historical adapter before any approved single-file retirement. Installation itself does not delete, restore, restart, cut over, or admit general cleanup. All existing backup, ownership, consumer, freshness, fallback, application acceptance and human-QA gates remain required.
