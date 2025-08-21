use dora_node_api::{
    DoraNode, Event,
    merged::{MergeExternal, MergedEvent}
};
use std::error::Error;
use dora_ros2_bridge::{
    messages::{
        customed_interfaces::service::{
            AddThreeInts,
            AddThreeIntsRequest,
            AddThreeIntsResponse
        },
    },
    ros2_client::{self, ros2, NodeOptions},
    rustdds::{self, policy},
};
use eyre::{eyre, Context};
use futures::task::SpawnExt;

fn main() -> Result<(), Box<dyn Error>> {
    let mut ros_node = init_ros_node()?;

    // spawn a background spinner task that is handles service discovery (and other things)
    let pool = futures::executor::ThreadPool::new()?;
    let spinner = ros_node
        .spinner()
        .map_err(|e| eyre::eyre!("failed to create spinner: {e:?}"))?;
    pool.spawn(async {
        if let Err(err) = spinner.spin().await {
            eprintln!("ros2 spinner failed: {err:?}");
        }
    }).context("failed to spawn ros2 spinner")?;

    // create an example service client
    let service_qos = {
        rustdds::QosPolicyBuilder::new()
            .reliability(policy::Reliability::Reliable {
                max_blocking_time: rustdds::Duration::from_millis(100),
            })
            .history(policy::History::KeepLast { depth: 1 })
            .build()
    };
    let add_server = ros_node.create_server::<AddThreeInts>(
        ros2_client::ServiceMapping::Enhanced,
        &ros2_client::Name::new("/dora", "add_three_ints").unwrap(),
        &ros2_client::ServiceTypeName::new("customed_interfaces", "AddThreeInts"),
        service_qos.clone(),
        service_qos.clone(),
    )?;

    let (mut node, dora_events) = DoraNode::init_from_env()?;

    let merged = dora_events.merge_external(Box::pin(add_server.receive_request_stream()));
    let mut events = futures::executor::block_on_stream(merged);

    loop {
        let event = match events.next() {
            Some(input) => input,
            None => break,
        };

        match event {
            MergedEvent::Dora(event) => match event {
                Event::Input {
                    id,
                    metadata: _,
                    data: _,
                } => match id.as_str() {
                    "tick" => {}
                    other => eprintln!("Ignoring unexpected input `{other}`"),
                },
                Event::Stop(_) => {
                    println!("Received stop");
                    break;
                },
                other => eprintln!("Received unexpected input: {other:?}"),
            },
            MergedEvent::External(add) => {
                println!("receive the {add:?}");
                if let Ok((req_id, req)) = add {
                    let sum = req.a + req.b + req.c;
                    println!("the sum is {sum}");
                    let resp = AddThreeIntsResponse {sum};
                    let sr = add_server.send_response(req_id, resp);
                    if let Err(e) = sr {
                        println!("Failed to send error {e:?}");
                    }
                }

            }
        }
    }

    Ok(())
}

fn init_ros_node() -> eyre::Result<ros2_client::Node> {
    let ros_context = ros2_client::Context::new().unwrap();

    ros_context
        .new_node(
            ros2_client::NodeName::new("/dora", "add_three_ints_server")
                .map_err(|e| eyre!("failed to create ROS2 node name: {e}"))?,
            NodeOptions::new().enable_rosout(true),
        )
        .map_err(|e| eyre::eyre!("failed to create ros2 node: {e:?}"))
}
