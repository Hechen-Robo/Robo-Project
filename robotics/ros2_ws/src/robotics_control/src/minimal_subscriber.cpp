#include "rclcpp/rclcpp.hpp"
#include "std_msgs/msg/string.hpp"

class MinimalSubscriber : public rclcpp::Node
{
public:
  MinimalSubscriber() : Node("minimal_subscriber")
  {
    subscription_ = create_subscription<std_msgs::msg::String>(
      "chatter", 10, std::bind(&MinimalSubscriber::on_message, this, std::placeholders::_1));
  }

private:
  void on_message(const std_msgs::msg::String::SharedPtr msg) const
  {
    RCLCPP_INFO(get_logger(), "I heard: '%s'", msg->data.c_str());
  }

  rclcpp::Subscription<std_msgs::msg::String>::SharedPtr subscription_;
};

int main(int argc, char * argv[])
{
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<MinimalSubscriber>());
  rclcpp::shutdown();
  return 0;
}
