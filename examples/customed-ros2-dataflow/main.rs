use dora_tracing::set_up_tracing;
use eyre::{Context, bail};
use std::{env, path::Path};
use tokio::process::Child;

#[tokio::main]
async fn main() -> eyre::Result<()> {
    set_up_tracing("rust-ros2-dataflow-runner").wrap_err("failed to set up tracing subscriber")?;

    let root = Path::new(env!("CARGO_MANIFEST_DIR"));
    std::env::set_current_dir(root.join(file!()).parent().unwrap())
        .wrap_err("failed to set working dir")?;

    install_ros_pkg().await?;

    let dataflow = Path::new("dataflow.yml");
    build_dataflow(dataflow).await?;
    let mut dataflow = run_dataflow(dataflow).await?;

    let mut ros_client = run_ros_pkg("add_client").await?;

    ros_client.wait().await?;
    dataflow.kill().await?;

    println!("Everything Done");

    Ok(())
}

async fn run_ros_pkg(node_name: &str) -> eyre::Result<Child> {
    let ros_path = if let Ok(path) = std::env::var("ROS") {
        path
    } else {
        String::from("/opt/ros/jazzy/setup.bash")
    };
    Ok(tokio::process::Command::new("bash").args(
        ["-c", &format!("source {ros_path}; source ./install/setup.bash; ros2 run customed_nodes {node_name}")]).spawn()?)
}

async fn install_ros_pkg() -> eyre::Result<()> {
    let ros_path = if let Ok(path) = std::env::var("ROS") {
        path
    } else {
        String::from("/opt/ros/jazzy/setup.bash")
    };
    let mut cmd = tokio::process::Command::new("bash");
    cmd.args(["-c",
        &format!("source {ros_path}; rosdep install --from-paths ./ -y --ignore-src; colcon build --symlink-install"),
    ]);
    if !cmd.status().await?.success() {
        bail!("failed to install related package");
    }
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
    Ok(cmd.spawn()?)
}
