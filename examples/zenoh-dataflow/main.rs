use dora_tracing::set_up_tracing;
use eyre::{Context, bail};
use std::path::Path;
use tokio::process::Child;

#[tokio::main]
async fn main() -> eyre::Result<()> {
    set_up_tracing("rust-dataflow-runner").wrap_err("failed to set up tracing subscriber")?;

    let root = Path::new(env!("CARGO_MANIFEST_DIR"));
    std::env::set_current_dir(root.join(file!()).parent().unwrap())
        .wrap_err("failed to set working dir")?;

    let args: Vec<String> = std::env::args().collect();
    let dataflow = if args.len() > 1 {
        Path::new(&args[1])
    } else {
        Path::new("dataflow.yml")
    };

    build_dataflow(dataflow).await?;

    let mut dataflow_proc = run_dataflow(dataflow).await?;
    let mut zenoh_proc = run_zenoh_app().await?;

    dataflow_proc.wait().await?;
    zenoh_proc.kill().await?;

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

async fn run_dataflow(dataflow: &Path) -> eyre::Result<Child> {
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
        .arg("--run-dataflow")
        .arg(dataflow);
    let child = cmd.spawn()?;
    Ok(child)
}

async fn run_zenoh_app() -> eyre::Result<Child> {
    let cargo = std::env::var("CARGO").unwrap();
    let mut cmd = tokio::process::Command::new(&cargo);
    cmd.arg("run");
    cmd.arg("--manifest-path")
        .arg(std::path::Path::new("./zenoh-app").join("Cargo.toml"));
    cmd.arg("--release");
    let child = cmd.spawn()?;
    Ok(child)
}
