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

    // Get argument for which example to run
    let args: Vec<String> = env::args().collect();
    let (dataflow_file, ros_pkg, dora_is_server) = if args.len() > 1 {
        match args[1].as_str() {
            "service" => ("dataflow.yml", "add_client", true),
            "action" => ("dataflow_action.yml", "fibonacci_server", false),
            other => {
                println!("Unknown example: {}. Using default service example.", other);
                ("dataflow.yml", "add_client", true)
            }
        }
    } else {
        // Default to service example
        ("dataflow.yml", "add_client", true)
    };

    println!("Running example with:");
    println!("  Dataflow file: {}", dataflow_file);
    println!("  ROS package: {}", ros_pkg);

    // Install ROS packages
    println!("Installing ROS packages...");
    install_ros_pkg().await?;

    // Check if dataflow file exists
    let dataflow = Path::new(dataflow_file);
    if !dataflow.exists() {
        bail!("Dataflow file '{}' not found", dataflow.display());
    }

    println!("Building dataflow: {}", dataflow.display());
    build_dataflow(dataflow).await?;
    let mut dataflow_process = run_dataflow(dataflow).await?;

    println!("Running ROS package: {}", ros_pkg);
    let mut ros_node = run_ros_pkg(ros_pkg).await?;

    // Different shutdown sequence based on whether Dora is server or client
    if dora_is_server {
        // When Dora is server, ROS client finishes first
        println!("Dora acting as server, waiting for ROS client to finish...");
        ros_node.wait().await?;
        println!("ROS client finished successfully");

        // Clean shutdown of Dora server
        println!("Shutting down Dora dataflow process...");
        dataflow_process.kill().await?;
    } else {
        // When Dora is client, we need to wait for ROS server to complete
        println!("Dora acting as client, waiting for ROS server to finish...");

        dataflow_process.wait().await?;

        println!("Shutting down ROS node...");
        ros_node.kill().await?;
    }

    println!("Everything Done");
    Ok(())
}

async fn run_ros_pkg(node_name: &str) -> eyre::Result<Child> {
    let ros_path = if let Ok(path) = std::env::var("ROS") {
        path
    } else {
        String::from("/opt/ros/jazzy/setup.bash")
    };

    println!("Executing ROS node: {}", node_name);
    let command = format!(
        "source {ros_path}; source ./install/setup.bash; ros2 run customed_nodes {node_name}"
    );

    let child = tokio::process::Command::new("bash")
        .args(["-c", &command])
        .spawn()?;

    println!("ROS node '{}' started successfully", node_name);
    Ok(child)
}

async fn install_ros_pkg() -> eyre::Result<()> {
    let ros_path = if let Ok(path) = std::env::var("ROS") {
        path
    } else {
        String::from("/opt/ros/jazzy/setup.bash")
    };

    println!("Installing ROS packages...");
    let mut cmd = tokio::process::Command::new("bash");
    cmd.args(["-c",
        &format!("source {ros_path}; rosdep install --from-paths ./ -y --ignore-src; colcon build --symlink-install"),
    ]);
    if !cmd.status().await?.success() {
        bail!("failed to install related package");
    }
    println!("ROS packages installed successfully");
    Ok(())
}

async fn build_dataflow(dataflow: &Path) -> eyre::Result<()> {
    let cargo = std::env::var("CARGO").unwrap_or_else(|_| "cargo".to_string());
    let dora = std::env::var("DORA").context("DORA environment variable not set")?;

    println!("Building dataflow: {}", dataflow.display());
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
    println!("Dataflow built successfully");
    Ok(())
}

async fn run_dataflow(dataflow: &Path) -> eyre::Result<Child> {
    let cargo = std::env::var("CARGO").unwrap_or_else(|_| "cargo".to_string());
    let dora = std::env::var("DORA").context("DORA environment variable not set")?;

    println!("Running dataflow: {}", dataflow.display());
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
    println!("Dataflow process started");
    Ok(child)
}
