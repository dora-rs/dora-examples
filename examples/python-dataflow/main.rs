use dora_tracing::set_up_tracing;
use eyre::{WrapErr, bail};
use std::path::{Path, PathBuf};

pub async fn run(program: &PathBuf, args: &[&str], pwd: Option<&Path>) -> eyre::Result<()> {
    let mut run = tokio::process::Command::new(program);
    run.args(args);

    if let Some(pwd) = pwd {
        run.current_dir(pwd);
    }
    if !run.status().await?.success() {
        eyre::bail!("failed to run {args:?}");
    };
    Ok(())
}

#[tokio::main]
async fn main() -> eyre::Result<()> {
    set_up_tracing("python-dataflow-runner")?;

    let root = Path::new(env!("CARGO_MANIFEST_DIR"));
    std::env::set_current_dir(root.join(file!()).parent().unwrap())
        .wrap_err("failed to set working dir")?;

    let uv = which::which("uv")
        .context("failed to find `uv`. Make sure to install it using: https://docs.astral.sh/uv/getting-started/installation/")?;

    run(&uv, &["venv", "-p", "3.11", "--seed"], None)
        .await
        .context("failed to create venv")?;

    let dora = std::env::var("DORA").unwrap();
    run(
        &uv,
        &[
            "pip",
            "install",
            "-e",
            &format!("{dora}/apis/python/node"),
            "--reinstall",
        ],
        None,
    )
    .await
    .context("Unable to install develop dora-rs API")?;

    let dataflow = Path::new("dataflow.yml");
    run_dataflow(dataflow).await?;

    Ok(())
}

async fn run_dataflow(dataflow: &Path) -> eyre::Result<()> {
    let cargo = std::env::var("CARGO").unwrap();

    // First build the dataflow (install requirements)
    let dora = std::env::var("DORA").unwrap();
    let mut cmd = tokio::process::Command::new(&cargo);
    cmd.arg("run");
    cmd.arg("--manifest-path")
        .arg(std::path::PathBuf::from(&dora).join("Cargo.toml"));
    cmd.arg("--package").arg("dora-cli");
    cmd.arg("--release");
    cmd.arg("--").arg("build").arg(dataflow).arg("--uv");
    if !cmd.status().await?.success() {
        bail!("failed to run dataflow");
    };

    let mut cmd = tokio::process::Command::new(&cargo);
    cmd.arg("run");
    cmd.arg("--manifest-path")
        .arg(std::path::PathBuf::from(&dora).join("Cargo.toml"));
    cmd.arg("--package").arg("dora-cli");
    cmd.arg("--release");
    cmd.arg("--").arg("run").arg(dataflow).arg("--uv");
    if !cmd.status().await?.success() {
        bail!("failed to run dataflow");
    };
    Ok(())
}
