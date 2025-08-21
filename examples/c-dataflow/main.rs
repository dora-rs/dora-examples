use dora_tracing::set_up_tracing;
use eyre::{bail, Context};
use std::{
    env::consts::{DLL_PREFIX, DLL_SUFFIX, EXE_SUFFIX},
    path::Path,
};

#[tokio::main]
async fn main() -> eyre::Result<()> {
    set_up_tracing("c-dataflow-runner").wrap_err("failed to set up tracing")?;
    
    let dora = std::path::PathBuf::from(std::env::var("DORA").unwrap());
    let root = Path::new(env!("CARGO_MANIFEST_DIR"));
    std::env::set_current_dir(root.join(file!()).parent().unwrap())
        .wrap_err("failed to set working dir")?;

    tokio::fs::create_dir_all("build").await?;

    build_package("dora-node-api-c").await?;

    tokio::fs::create_dir_all("build").await?;
    let build_dir = Path::new("build");
    tokio::fs::copy(
        dora.join("apis/c/node/node_api.h"),
        build_dir.join("node_api.h"),
    )
    .await?;
    
    build_c_node(&dora, "node.c", "c_node").await?;
    build_c_node(&dora, "sink.c", "c_sink").await?;
    build_c_node(&dora, "counter.c", "c_counter").await?;

    let dataflow = Path::new("dataflow.yml").to_owned();
    run_dataflow(&dataflow).await?;

    Ok(())
}

async fn build_package(package: &str) -> eyre::Result<()> {
    let dora = std::env::var("DORA").unwrap();
    let cargo = std::env::var("CARGO").unwrap();
    
    let mut cmd = tokio::process::Command::new("bash");
    let manifest = std::path::PathBuf::from(dora).join("Cargo.toml");
    let manifest = manifest.to_str().unwrap();
    cmd.args(["-c",
        &format!("cargo build --release --manifest-path {manifest} --package {package}",
  )]);
    if !cmd.status().await?.success() {
        bail!("failed to compile {package}");
    };
    Ok(())
}

async fn run_dataflow(dataflow: &Path) -> eyre::Result<()> {
    let cargo = std::env::var("CARGO").unwrap();
    let dora = std::env::var("DORA").unwrap();
    let mut cmd = tokio::process::Command::new(&cargo);
    cmd.arg("run");
    cmd.arg("--manifest-path").arg(std::path::PathBuf::from(dora).join("Cargo.toml"));
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

async fn build_c_node(dora: &Path, name: &str, out_name: &str) -> eyre::Result<()> {
    let mut clang = tokio::process::Command::new("clang");
    clang.arg(name);
    clang.arg("-l").arg("dora_node_api_c");
    #[cfg(target_os = "linux")]
    {
        clang.arg("-l").arg("m");
        clang.arg("-l").arg("rt");
        clang.arg("-l").arg("dl");
        clang.arg("-l").arg("z");
        clang.arg("-pthread");
    }
    #[cfg(target_os = "windows")]
    {
        clang.arg("-ladvapi32");
        clang.arg("-luserenv");
        clang.arg("-lkernel32");
        clang.arg("-lws2_32");
        clang.arg("-lbcrypt");
        clang.arg("-lncrypt");
        clang.arg("-lschannel");
        clang.arg("-lntdll");
        clang.arg("-liphlpapi");

        clang.arg("-lcfgmgr32");
        clang.arg("-lcredui");
        clang.arg("-lcrypt32");
        clang.arg("-lcryptnet");
        clang.arg("-lfwpuclnt");
        clang.arg("-lgdi32");
        clang.arg("-lmsimg32");
        clang.arg("-lmswsock");
        clang.arg("-lole32");
        clang.arg("-loleaut32");
        clang.arg("-lopengl32");
        clang.arg("-lsecur32");
        clang.arg("-lshell32");
        clang.arg("-lsynchronization");
        clang.arg("-luser32");
        clang.arg("-lwinspool");
        clang.arg("-lwinhttp");
        clang.arg("-lrpcrt4");

        clang.arg("-Wl,-nodefaultlib:libcmt");
        clang.arg("-D_DLL");
        clang.arg("-lmsvcrt");
    }
    #[cfg(target_os = "macos")]
    {
        clang.arg("-framework").arg("CoreServices");
        clang.arg("-framework").arg("Security");
        clang.arg("-l").arg("System");
        clang.arg("-l").arg("resolv");
        clang.arg("-l").arg("pthread");
        clang.arg("-l").arg("c");
        clang.arg("-l").arg("m");
        clang.arg("-l").arg("z");
    }
    clang.arg("-L").arg(dora.join("target").join("release"));
    clang
        .arg("--output")
        .arg(Path::new("build").join(format!("{out_name}{EXE_SUFFIX}")));
    if !clang.status().await?.success() {
        bail!("failed to compile c node");
    };
    Ok(())
}
