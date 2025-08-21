#include "rclcpp/rclcpp.hpp"
#include "customed_interfaces/srv/add_three_ints.hpp"

#include <chrono>
#include <memory>
#include <random>

using namespace std::chrono_literals;

int main(int argc, char **argv)
{
  std::random_device rd;
  std::mt19937 generator(rd());
  rclcpp::init(argc, argv);

  std::shared_ptr<rclcpp::Node> node = rclcpp::Node::make_shared("ros_add_three_ints_client");
  rclcpp::Client<customed_interfaces::srv::AddThreeInts>::SharedPtr client =
    node->create_client<customed_interfaces::srv::AddThreeInts>("/dora/add_three_ints");

  for (size_t i = 0; i < 10; ++i) {
    auto request = std::make_shared<customed_interfaces::srv::AddThreeInts::Request>();
    request->a = generator();
    request->b = generator();
    request->c = generator();
    int64_t sum = request->a + request->b + request->c;

    while (!client->wait_for_service(1s)) {
      if (!rclcpp::ok()) {
        RCLCPP_ERROR(rclcpp::get_logger("rclcpp"), "Interrupted while waiting for the service. Exiting.");
        return 0;
      }
      RCLCPP_INFO(rclcpp::get_logger("rclcpp"), "service not available, waiting again...");
    }

    auto result = client->async_send_request(request);
    // Wait for the result.
    if (rclcpp::spin_until_future_complete(node, result) ==
        rclcpp::FutureReturnCode::SUCCESS)
      {
        int64_t res_sum = result.get()->sum;
        RCLCPP_INFO(rclcpp::get_logger("rclcpp"), "sum: %ld, recv_sum: %ld", sum, res_sum);
        assert(sum == res_sum);
      } else {
      RCLCPP_ERROR(rclcpp::get_logger("rclcpp"), "Failed to call service add_two_ints");
    }
  }
  rclcpp::shutdown();
  return 0;
}
