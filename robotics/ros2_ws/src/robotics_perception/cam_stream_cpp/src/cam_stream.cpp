#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/msg/image.hpp>
#include <image_transport/image_transport.hpp>
#include <cv_bridge/cv_bridge.h>
#include <opencv2/opencv.hpp>

class CamStreamNode : public rclcpp::Node
{
public:
  CamStreamNode() : Node("cam_stream_cpp")
  {
    // 1) declare params
    this->declare_parameter<std::string>("camera_source", "/dev/video0");
    this->declare_parameter<std::string>("frame_id", "camera_link");
    this->declare_parameter<double>("publish_rate", 30.0);
    // 2) read params
    camera_source_ = this->get_parameter("camera_source").as_string();
    frame_id_ = this->get_parameter("frame_id").as_string();
    publish_rate_ = this->get_parameter("publish_rate").as_double();
    // 3) create pub/sub
    pub_ = image_transport::create_publisher(this, "camera/image_raw");
    // 4) Open Camera
    open_camera(camera_source_);
    // 5) create timer/*  */
    using namespace std::chrono_literals;
    timer_ = this->create_wall_timer(
        std::chrono::duration<double>(1.0 / publish_rate_),
        std::bind(&CamStreamNode::on_timer, this));
    RCLCPP_INFO(this->get_logger(), "Cam stream node started");
  }

private:
  void open_camera(const std::string &src)
  {
    bool is_number = !src.empty() && std::all_of(src.begin(), src.end(), ::isdigit);

    if (is_number)
    {
      int index = std::stoi(src);
      cap_.open(index);

      // Force MJPG
      cap_.set(cv::CAP_PROP_FOURCC, cv::VideoWriter::fourcc('M', 'J', 'P', 'G'));
      // Force resolution
      cap_.set(cv::CAP_PROP_FRAME_WIDTH, 1280);
      cap_.set(cv::CAP_PROP_FRAME_HEIGHT, 960);
      // Force FPS
      cap_.set(cv::CAP_PROP_FPS, 30);
    }
    else
    {
      cap_.open(src);
    }
    if (!cap_.isOpened())
    {
      throw std::runtime_error("Failed to open camera source:" + src);
    }
  }
  void on_timer()
  {
    cv::Mat frame;
    if (!cap_.read(frame))
    {
      RCLCPP_WARN(this->get_logger(), "Failed to read frame from camera");
      return;
    }
    auto msg = cv_bridge::CvImage(std_msgs::msg::Header(), "bgr8", frame).toImageMsg();
    msg->header.frame_id = frame_id_;
    msg->header.stamp = this->now();
    pub_.publish(msg);
  }

private:
  std::string camera_source_;
  std::string frame_id_;
  double publish_rate_{30.0};
  image_transport::Publisher pub_;
  cv::VideoCapture cap_;
  rclcpp::TimerBase::SharedPtr timer_;
};

int main(int argc, char **argv)
{
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<CamStreamNode>());
  rclcpp::shutdown();
  return 0;
}