use dora_node_api::{
    DoraNode, Event,
    merged::{MergeExternal, MergedEvent},
};
use dora_ros2_bridge::{
    messages::customed_interfaces::action::{
        Fibonacci, FibonacciFeedback, FibonacciGoal, FibonacciResult,
    },
    ros2_client::{
        self, NodeOptions,
        action::{ActionClientQosPolicies, GoalId},
    },
    rustdds::{self, policy},
};
use eyre::{Context, eyre};
use futures::{Stream, StreamExt, pin_mut, task::SpawnExt};
use serde_json::json;
use std::{error::Error, pin::Pin, sync::Arc};
use tokio::sync::mpsc;

fn main() -> Result<(), Box<dyn Error>> {
    let mut ros_node = init_ros_node()?;

    // spawn a background spinner task that handles service discovery (and other things)
    // Create a thread pool for async tasks and wrap it in Arc for sharing
    let pool = Arc::new(futures::executor::ThreadPool::new()?);
    let spinner = ros_node
        .spinner()
        .map_err(|e| eyre::eyre!("failed to create spinner: {e:?}"))?;
    pool.spawn(async {
        if let Err(err) = spinner.spin().await {
            eprintln!("ros2 spinner failed: {err:?}");
        }
    })
    .context("failed to spawn ros2 spinner")?;

    // create an example service client
    let qos = rustdds::QosPolicyBuilder::new()
        .reliability(policy::Reliability::Reliable {
            max_blocking_time: rustdds::Duration::from_millis(100),
        })
        .history(policy::History::KeepLast { depth: 1 })
        .build();
    let action_qos = ActionClientQosPolicies {
        goal_service: qos.clone(),
        result_service: qos.clone(),
        cancel_service: qos.clone(),
        feedback_subscription: qos.clone(),
        status_subscription: qos.clone(),
    };
    let fib_client = Arc::new(ros_node.create_action_client::<Fibonacci>(
        ros2_client::ServiceMapping::Enhanced,
        &ros2_client::Name::new("/", "fibonacci").unwrap(),
        &ros2_client::ActionTypeName::new("customed_interfaces", "Fibonacci"),
        action_qos,
    )?);

    // Create channels for Fibonacci action events
    let (tx, rx) = mpsc::channel(10);
    let tx = Arc::new(tx);

    // Create a stream from ROS2 action events
    let action_stream = ActionEventStream::new(rx);

    let (node, dora_events) = DoraNode::init_from_env()?;

    println!("ROS2 Fibonacci action client initialized and ready");

    // Merge Dora events with our action events
    let merged = dora_events.merge_external(Box::pin(action_stream));
    let mut events = futures::executor::block_on_stream(merged);
    let mut requesting = false;

    loop {
        let event = match events.next() {
            Some(input) => input,
            None => break,
        };

        match event {
            MergedEvent::Dora(event) => {
                match event {
                    Event::Input {
                        id,
                        metadata: _,
                        data: _,
                    } => {
                        match id.as_str() {
                            "tick" => {
                                if requesting {
                                    break;
                                }

                                println!("Received tick, sending Fibonacci goal");

                                // Hardcode the order value as 10
                                let order = 10;

                                println!("Sending Fibonacci goal with order: {}", order);

                                // Clone action client and sender for use in async task
                                let client = fib_client.clone();
                                let tx_clone = tx.clone();

                                // Spawn a task to initiate the goal and set up the event pipeline
                                let pool_clone = pool.clone();
                                pool_clone
                                    .clone()
                                    .spawn(async move {
                                        let goal = FibonacciGoal { order };
                                        match client.async_send_goal(goal).await {
                                            Ok((goal_id, response)) => {
                                                if response.accepted {
                                                    // Send acceptance event
                                                    let _ = tx_clone
                                                        .clone()
                                                        .send(FibonacciEvent::Accepted {
                                                            goal_id,
                                                            order,
                                                        })
                                                        .await;

                                                    // Set up feedback handling
                                                    let feedback_tx = tx_clone.clone();
                                                    let client_clone = client.clone();

                                                    // Spawn a task to handle feedback
                                                    pool_clone.clone().spawn(async move {
                                                        let feedback_stream =
                                                            client_clone.feedback_stream(goal_id);
                                                        pin_mut!(feedback_stream);
                                                        while let Some(feedback_result) =
                                                        feedback_stream.next().await
                                                        {
                                                            if let Ok(feedback) = feedback_result {
                                                                let _ = feedback_tx
                                                                    .clone()
                                                                    .send(FibonacciEvent::Feedback {
                                                                        feedback,
                                                                    })
                                                                    .await;
                                                            }
                                                        }
                                                    })
                                                    .unwrap_or_else(|e| {
                                                        eprintln!(
                                                            "Failed to spawn feedback handler: {:?}",
                                                            e
                                                        )
                                                    });

                                                    // Request and wait for the result
                                                    match client.async_request_result(goal_id).await
                                                    {
                                                        Ok((status, result)) => {
                                                            let sequence = result.sequence.clone();
                                                            let _ = tx_clone
                                                                .clone()
                                                                .send(FibonacciEvent::Result {
                                                                    result,
                                                                })
                                                                .await;
                                                        }
                                                        Err(e) => {
                                                            let _ = tx_clone
                                                                .clone()
                                                                .send(FibonacciEvent::Error {
                                                                    message: format!(
                                                                        "Failed to get result: {:#?}",
                                                                        e
                                                                    ),
                                                                })
                                                                .await;
                                                        }
                                                    }
                                                } else {
                                                    // Goal was rejected
                                                    let _ = tx_clone
                                                        .clone()
                                                        .send(FibonacciEvent::Error {
                                                            message:
                                                            "Goal rejected by the action server"
                                                                .to_string(),
                                                        })
                                                        .await;
                                                }
                                            }
                                            Err(e) => {
                                                let _ = tx_clone
                                                    .clone()
                                                    .send(FibonacciEvent::Error {
                                                        message: format!(
                                                            "Failed to initiate goal: {:#?}",
                                                            e
                                                        ),
                                                    })
                                                    .await;
                                            }
                                        }
                                    })
                                    .unwrap_or_else(|e| {
                                        eprintln!("Failed to spawn goal handler task: {:?}", e)
                                    });
                            }
                            other => eprintln!("Ignoring unexpected input `{other}`"),
                        }
                    }
                    Event::Stop(_) => {
                        println!("Received stop");
                        break;
                    }
                    other => eprintln!("Received unexpected input: {other:?}"),
                }
            }
            MergedEvent::External(event) => match event {
                FibonacciEvent::Accepted { goal_id, order } => {
                    requesting = true;
                    println!(
                        "Fibonacci calculation started for order {}, goal_id: {:#?}",
                        order, goal_id
                    );
                }
                FibonacciEvent::Feedback { feedback } => {
                    println!("Received Fibonacci feedback: {:#?}", feedback);
                }
                FibonacciEvent::Result { result } => {
                    println!(
                        "Fibonacci calculation completed. Final result is {:#?}",
                        result
                    );
                    break;
                }
                FibonacciEvent::Error { message } => {
                    eprintln!("Fibonacci action error: {}", message);
                }
            },
        }
    }

    Ok(())
}

fn init_ros_node() -> eyre::Result<ros2_client::Node> {
    let ros_context = ros2_client::Context::new()
        .map_err(|e| eyre::eyre!("failed to create ROS2 context: {e:?}"))?;

    ros_context
        .new_node(
            ros2_client::NodeName::new("/dora", "fibonacci_action_client")
                .map_err(|e| eyre!("failed to create ROS2 node name: {e}"))?,
            NodeOptions::new().enable_rosout(true),
        )
        .map_err(|e| eyre::eyre!("failed to create ros2 node: {e:?}"))
}

// Define the events we'll use for Fibonacci action client
enum FibonacciEvent {
    Accepted { goal_id: GoalId, order: i32 },
    Feedback { feedback: FibonacciFeedback },
    Result { result: FibonacciResult },
    Error { message: String },
}

// Stream adapter for Fibonacci events
struct ActionEventStream {
    receiver: mpsc::Receiver<FibonacciEvent>,
}

impl ActionEventStream {
    fn new(receiver: mpsc::Receiver<FibonacciEvent>) -> Self {
        Self { receiver }
    }
}

impl Stream for ActionEventStream {
    type Item = FibonacciEvent;

    fn poll_next(
        mut self: Pin<&mut Self>,
        cx: &mut std::task::Context<'_>,
    ) -> std::task::Poll<Option<Self::Item>> {
        Pin::new(&mut self.receiver).poll_recv(cx)
    }
}
