use dora_node_api::{
    self, DoraNode, Event,
    merged::{MergeExternal, MergedEvent},
};
use eyre::eyre;
use zenoh::bytes::Encoding;
use zenoh::{Wait, config::Config};

/// The zenoh app receives 5 msgs from dora node first.
/// Then, zenoh app's publication starts.
/// After the dora node receive 5 msgs from zenoh app,
/// dora node ends itself
fn main() -> eyre::Result<()> {
    // Initialize the Dora node
    let (_node, events) = DoraNode::init_from_env()?;

    // Initialize Zenoh
    println!("Initializing Zenoh session...");
    let zenoh_config = Config::default();
    let session = zenoh::open(zenoh_config)
        .wait()
        .map_err(|e| eyre!("Failed to open Zenoh session: {}", e))?;

    println!("Declaring Zenoh publisher for 'dora/data'...");
    let publisher = session.declare_publisher("dora/data").wait().unwrap();

    // Set up a subscriber to receive messages
    println!("Declaring Zenoh subscriber for 'zenoh/data'...");
    let subscriber = session.declare_subscriber("zenoh/data").wait().unwrap();

    println!("Dora node with Zenoh integration started!");

    // Counter for message numbering
    let mut counter = 0;

    let zenoh_stream = subscriber.stream();

    // Merge Dora events with Zenoh events
    let merged = events.merge_external(Box::pin(zenoh_stream));

    // Use block_on_stream to process the merged events in a non-async context
    let mut merged_events = futures::executor::block_on_stream(merged);

    let mut counter = 0;
    while let Some(event) = merged_events.next() {
        match event {
            MergedEvent::Dora(event) => match event {
                Event::Input {
                    id,
                    metadata: _,
                    data: _,
                } => match id.as_str() {
                    "tick" => {
                        // Increment counter for message numbering
                        counter += 1;

                        // Create a simple hello message
                        let message = format!("Hello from Dora node! Message #{}", counter);

                        // Publish to Zenoh
                        println!("Publishing message: {}", message);
                        publisher
                            .put(message)
                            .encoding(Encoding::TEXT_PLAIN)
                            .wait()
                            .map_err(|e| eyre!("Failed to publish data: {}", e))?;

                        // Also output to Dora
                    }
                    other => eprintln!("Ignoring unexpected input `{other}`"),
                },
                Event::Stop(_) => {
                    println!("Received stop");
                    break;
                }
                Event::InputClosed { id } => {
                    println!("Input `{id}` was closed");
                }
                other => eprintln!("Received unexpected input: {other:?}"),
            },
            MergedEvent::External(sample) => {
                let payload = sample
                    .payload()
                    .try_to_string()
                    .unwrap_or_else(|e| e.to_string().into());
                print!(
                    ">> [Subscriber] Received {} ('{}': '{}')",
                    sample.kind(),
                    sample.key_expr().as_str(),
                    payload
                );
                println!();
                counter += 1;
                if counter > 5 {
                    break;
                }
            }
        }
    }

    Ok(())
}
