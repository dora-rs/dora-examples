use dora_tracing::set_up_tracing;
use eyre::{Context, bail};
use std::path::Path;
use tokio::process::Child;

#[tokio::main]
async fn main() -> eyre::Result<()> {
    set_up_tracing("rust-ros2-dataflow-runner").wrap_err("failed to set up tracing subscriber")?;

    install_ros_pkg().await?;

    let root = Path::new(env!("CARGO_MANIFEST_DIR"));
    std::env::set_current_dir(root.join(file!()).parent().unwrap())
        .wrap_err("failed to set working dir")?;

    let dataflow = Path::new("dataflow.yml");
    build_dataflow(dataflow).await?;

    let ros_node = run_ros_pkg().await?;

    run_dataflow(dataflow).await?;

    for mut node in ros_node {
        node.kill().await?;
    }

    println!("Everything Done");

    Ok(())
}

async fn run_ros_pkg() -> eyre::Result<Vec<Child>> {
    let mut ros_node = vec![];
    let ros_path = if let Ok(path) = std::env::var("ROS") {
        path
    } else {
        String::from("/opt/ros/jazzy/setup.bash")
    };
    ros_node.push(
        tokio::process::Command::new("bash")
            .args([
                "-c",
                &format!("source {ros_path}; ros2 run turtlesim turtlesim_node"),
            ])
            .spawn()?,
    );
    ros_node.push(
        tokio::process::Command::new("bash")
            .args([
                "-c",
                &format!(
                    "source {ros_path}; ros2 run examples_rclcpp_minimal_service service_main"
                ),
            ])
            .spawn()?,
    );
    Ok(ros_node)
}

async fn install_ros_pkg() -> eyre::Result<()> {
    let mut cmd = tokio::process::Command::new("bash");
    cmd.args(["-c",
        "sudo apt update && sudo apt install -y ros-jazzy-turtlesim ros-jazzy-examples-rclcpp-minimal-service
",
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

async fn run_dataflow(dataflow: &Path) -> eyre::Result<()> {
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
    if !cmd.status().await?.success() {
        bail!("failed to run dataflow");
    };
    Ok(())
}
