use std::time::Duration;
use zenoh::bytes::Encoding;

#[tokio::main]
async fn main() {
    // Using hardcoded parameters
    let selector = "dora/data";
    let publish_topic = "zenoh/data";

    println!("Zenoh App - Will subscribe to: {}", selector);

    // Initialize Zenoh
    println!("Opening Zenoh session...");
    let config = zenoh::config::Config::default();
    let session = zenoh::open(config).await.unwrap();

    // Subscribe to the topic
    println!("Subscribing to {}...", selector);
    let subscriber = session.declare_subscriber(selector).await.unwrap();

    // Start publishing messages
    let mut count = 0;
    while let Ok(sample) = subscriber.recv_async().await {
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
        count += 1;
        if count > 5 {
            break;
        }
    }

    // Create a publisher for sending messages to Dora
    println!("Creating publisher for '{}'...", publish_topic);
    let publisher = session.declare_publisher(publish_topic).await.unwrap();

    let mut counter = 0;
    loop {
        tokio::time::sleep(Duration::from_secs(1)).await;
        let buf = format!("Hello, payload counter: {counter}");
        println!("sent payload(counter = {counter})");
        publisher
            .put(buf)
            .encoding(Encoding::TEXT_PLAIN)
            .await
            .unwrap();
        counter += 1;
    }
}
