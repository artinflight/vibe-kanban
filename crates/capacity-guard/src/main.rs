//! Runs INSIDE the scheduled execution's systemd unit. Codex inherits the RPC
//! pipes directly; guard failure/exit causes systemd to kill the entire cgroup.
//! A separate RuntimeMaxSec deadline protects even a stalled guard process.
#[cfg(unix)]
fn main() {
    if let Err(error) = run() {
        eprintln!("Capacity execution stopped: {error}");
        std::process::exit(75);
    }
}

#[cfg(not(unix))]
fn main() {
    eprintln!("Scheduled capacity execution requires Linux systemd containment");
    std::process::exit(75);
}

#[cfg(unix)]
fn run() -> std::io::Result<()> {
    use std::{
        env,
        fs::OpenOptions,
        io::{self, Write},
        os::unix::{fs::OpenOptionsExt, process::CommandExt},
        path::PathBuf,
        process::{Command, Stdio},
        thread,
        time::{Duration, Instant, SystemTime, UNIX_EPOCH},
    };

    use capacity_guard::{Fence, read_lease};
    let wall = || {
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_millis() as u64
    };
    let mut args = env::args_os().skip(1);
    let file = PathBuf::from(
        args.next()
            .ok_or_else(|| io::Error::other("missing permission file"))?,
    );
    let program = args
        .next()
        .ok_or_else(|| io::Error::other("missing executable"))?;
    // Reject uncontained invocation. systemd sets INVOCATION_ID for service
    // processes; integration also supplies an independent RuntimeMaxSec.
    if env::var_os("INVOCATION_ID").is_none() {
        return Err(io::Error::other(
            "capacity guard must run in a systemd service",
        ));
    }
    let started = Instant::now();
    let lease = read_lease(&file)?;
    let mut fence = Fence::new(lease.clone(), wall(), 0).map_err(io::Error::other)?;
    // Create once BEFORE launching the child. A restart with this permission is
    // forbidden even if the first guard died before it could write a final receipt.
    let mut marker = OpenOptions::new()
        .write(true)
        .create_new(true)
        .mode(0o600)
        .open(file.with_extension("started"))?;
    marker.write_all(lease.id.as_bytes())?;
    marker.sync_all()?;
    std::fs::File::open(
        file.parent()
            .ok_or_else(|| io::Error::other("missing permission directory"))?,
    )?
    .sync_all()?;
    fence
        .observe(
            &read_lease(&file)?,
            wall(),
            started.elapsed().as_millis() as u64,
        )
        .map_err(io::Error::other)?;
    let mut child = Command::new(program)
        .args(args)
        .stdin(Stdio::inherit())
        .stdout(Stdio::inherit())
        .stderr(Stdio::inherit())
        .process_group(0)
        .spawn()?;
    let reason = loop {
        if let Some(status) = child.try_wait()? {
            if status.success() {
                return Ok(());
            }
            return Err(io::Error::other("scheduled child exited unsuccessfully"));
        }
        let check = read_lease(&file).and_then(|next| {
            fence
                .observe(&next, wall(), started.elapsed().as_millis() as u64)
                .map_err(io::Error::other)
        });
        if let Err(error) = check {
            break error;
        }
        thread::sleep(Duration::from_millis(100));
    };
    // Stop promptly without waiting for a model/tool turn to finish. Native
    // pause+interrupt is attempted by VK earlier; this is the independent fallback.
    let group = -(child.id() as i32);
    unsafe {
        libc::kill(group, libc::SIGTERM);
    }
    thread::sleep(Duration::from_millis(250));
    unsafe {
        libc::kill(group, libc::SIGKILL);
    }
    let _ = child.wait();
    // Returning stops the main service process. KillMode=control-group also
    // catches descendants which used setsid() to leave the original group.
    Err(reason)
}
