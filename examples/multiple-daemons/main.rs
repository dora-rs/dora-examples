use dora_tracing::TracingBuilder;
use eyre::{Context, OptionExt, bail};

use std::{net::Ipv4Addr, path::Path};
use tokio::task::JoinSet;

#[tokio::main]
async fn main() -> eyre::Result<()> {
    TracingBuilder::new("multiple-daemon-runner")
        .with_stdout("debug")
        .build()?;

    let root = Path::new(env!("CARGO_MANIFEST_DIR"));
    std::env::set_current_dir(root.join(file!()).parent().unwrap())
        .wrap_err("failed to set working dir")?;

    let dataflow = Path::new("dataflow.yml");
    build_dataflow(dataflow).await?;

    let coordinator_addr = Ipv4Addr::LOCALHOST;
    let interface_port =
        port_check::free_local_ipv4_port_in_range(10000..=15000).ok_or_eyre("No available port")?;
    let control_port = port_check::free_local_ipv4_port_in_range((interface_port + 1)..=15000)
        .ok_or_eyre("No available port")?;
    let coordinator = run_coordinator(coordinator_addr.to_string(), interface_port, control_port);
    let daemon_a = run_daemon(coordinator_addr.to_string(), "A", interface_port);
    let daemon_b = run_daemon(coordinator_addr.to_string(), "B", interface_port);

    tracing::info!("Spawning coordinator and daemons");
    let mut tasks = JoinSet::new();
    tasks.spawn(coordinator);
    tasks.spawn(daemon_b);
    tasks.spawn(daemon_a);

    // tracing::info!("waiting until daemons are connected to coordinator");

    tracing::info!("starting dataflow");
    let dataflow_task = start_dataflow(dataflow, coordinator_addr.to_string(), interface_port);

    tasks.spawn(dataflow_task);

    tracing::info!("joining tasks");
    while let Some(res) = tasks.join_next().await {
        res.unwrap()?;
    }

    tracing::info!("done");
    Ok(())
}

async fn start_dataflow(
    dataflow: &Path,
    coordinator_addr: String,
    coordinator_port: u16,
) -> eyre::Result<()> {
    let cargo = std::env::var("CARGO").unwrap();
    let dora = std::env::var("DORA").unwrap();
    let mut cmd = tokio::process::Command::new(&cargo);
    cmd.arg("run");
    cmd.arg("--manifest-path")
        .arg(std::path::PathBuf::from(dora).join("Cargo.toml"));
    cmd.arg("--package").arg("dora-cli");
    cmd.arg("--release");
    cmd.arg("--").arg("start").arg(dataflow).args([
        "--coordinator-addr",
        &coordinator_addr,
        "--coordinator-port",
        &coordinator_port.to_string(),
    ]);
    if !cmd.status().await?.success() {
        bail!("failed to build dataflow");
    };
    Ok(())
}

async fn build_dataflow(dataflow: &Path) -> eyre::Result<()> {
    let cargo = std::env::var("CARGO").unwrap();
    let dora = std::env::var("DORA").unwrap();
    let mut cmd = tokio::process::Command::new(&cargo);
    cmd.arg("run");
    cmd.arg("--manifest-path")
        .arg(std::path::PathBuf::from(dora).join("Cargo.toml"));
    cmd.arg("--package").arg("dora-cli");
    cmd.arg("--release");
    cmd.arg("--").arg("build").arg(dataflow);
    if !cmd.status().await?.success() {
        bail!("failed to build dataflow");
    };
    Ok(())
}

async fn run_coordinator(
    interface: String,
    interface_port: u16,
    control_port: u16,
) -> eyre::Result<()> {
    let cargo = std::env::var("CARGO").unwrap();
    let dora = std::env::var("DORA").unwrap();
    let mut cmd = tokio::process::Command::new(&cargo);
    cmd.arg("run");
    cmd.arg("--manifest-path")
        .arg(std::path::PathBuf::from(dora).join("Cargo.toml"));
    cmd.arg("--package").arg("dora-cli");
    cmd.arg("--release");
    cmd.arg("--").arg("coordinator").args([
        "--interface",
        &interface,
        "--control-interface",
        &interface,
        "--port",
        &interface_port.to_string(),
        "--control-port",
        &control_port.to_string(),
    ]);
    if !cmd.status().await?.success() {
        bail!("failed to run dataflow");
    };
    Ok(())
}

async fn run_daemon(
    coordinator: String,
    machine_id: &str,
    interface_port: u16,
) -> eyre::Result<()> {
    let daemon_port =
        port_check::free_local_ipv4_port_in_range(11000..=15000).ok_or_eyre("No available port")?;
    let cargo = std::env::var("CARGO").unwrap();
    let dora = std::env::var("DORA").unwrap();
    let mut cmd = tokio::process::Command::new(&cargo);
    cmd.arg("run");
    cmd.arg("--manifest-path")
        .arg(std::path::PathBuf::from(dora).join("Cargo.toml"));
    cmd.arg("--package").arg("dora-cli");
    cmd.arg("--release");
    cmd.arg("--")
        .arg("daemon")
        .arg("--machine-id")
        .arg(machine_id)
        .arg("--coordinator-addr")
        .arg(coordinator)
        .arg("--coordinator-port")
        .arg(interface_port.to_string())
        .arg("--local-listen-port")
        .arg(daemon_port.to_string()); // random port
    if !cmd.status().await?.success() {
        bail!("failed to run dataflow");
    };
    Ok(())
}
