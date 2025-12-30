#include <rclcpp/rclcpp.hpp>
#include <opencv2/opencv.hpp>
#include <string>
#include <sensor_msgs/msg/image.hpp>
#include <cv_bridge/cv_bridge.h>

class YoloNode : public rclcpp::Node
{
public:
    YoloNode() : Node("yolo_cpp")
    {
        // 1) declare params
        // this->declare_parameter<std::string>("model_path", "yolov4-tiny.weights");
        // this->declare_parameter<std::string>("config_path", "yolov4-tiny.cfg");
        // this->declare_parameter<std::string>("class_names_path", "coco.names");
        // this->declare_parameter<double>("detection_threshold", 0.5);
        // 2) read params
        // model_path_ = this->get_parameter("model_path").as_string();
        // config_path_ = this->get_parameter("config_path").as_string();
        // class_names_path_ = this->get_parameter("class_names_path").as_string();
        // detection_threshold_ = this->get_parameter("detection_threshold").as_double();

        // 3） create subscriber
        sub_ = this->create_subscription<sensor_msgs::msg::Image>("/camera/image_raw", 10, std::bind(&YoloNode::on_image, this, std::placeholders::_1));
        RCLCPP_INFO(this->get_logger(), "YOLO node started. Subscribing /camera/image_raw");
    }

private:
    void on_image(const sensor_msgs::msg::Image::SharedPtr msg)
    {
        // Convert ROS image to OpenCV image
        cv::Mat frame = cv_bridge::toCvCopy(msg, "bgr8")->image;

        RCLCPP_INFO_THROTTLE(this->get_logger(), *this->get_clock(), 2000, "Got image %dx%d", frame.cols, frame.rows);
    }
    rclcpp::Subscription<sensor_msgs::msg::Image>::SharedPtr sub_;
    // std::string model_path_;
    // std::string config_path_;
    // std::string class_names_path_;
    // double detection_threshold_;
};

int main(int argc, char **argv)
{
    rclcpp::init(argc, argv);
    auto node = std::make_shared<YoloNode>();
    rclcpp::spin(node);
    rclcpp::shutdown();
    return 0;
}
