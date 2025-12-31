import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import cv2
import os
from vision_msgs.msg import Detection2DArray, Detection2D, ObjectHypothesisWithPose

from ultralytics import YOLO # type: ignore

class YoloNode(Node):
    def __init__(self):
        super().__init__("yolo_py")

        self.declare_parameter("image_topic", "/camera/image_raw")
        self.declare_parameter("model", "yolov8n.pt")
        self.declare_parameter("conf", 0.5)
        self.declare_parameter("device", "cpu")

        self.image_topic = self.get_parameter("image_topic").get_parameter_value().string_value
        model_path = self.get_parameter("model").get_parameter_value().string_value
        self.conf = self.get_parameter("conf").get_parameter_value().double_value
        self.device = self.get_parameter("device").get_parameter_value().string_value

        if os.path.isabs(model_path) and (not os.path.exists(model_path)):
            raise FileNotFoundError(f"Model file not found: {model_path}")
       
        self.model = YOLO(model_path)
        self.get_logger().info(f"Loaded model from {model_path} on device {self.device}")

        self.bridge = CvBridge()
        self.det_pub = self.create_publisher(Detection2DArray, '/yolo/detections', 10)
        self.pub = self.create_publisher(Image, "/yolo/image", 10)
        self.sub = self.create_subscription(
            Image,
            self.image_topic,
            self.on_image,
            10
        )

    def on_image(self, msg):
        frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        frame = cv2.flip(frame, 1)

        results = self.model(frame, conf=self.conf, device=self.device, verbose=False)[0]
        det_arr = Detection2DArray()
        det_arr.header = msg.header
        # results.boxes: xyxy + conf + cls
        for box in results.boxes:
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            conf = float(box.conf[0])
            cls_id = int(box.cls[0])

            det = Detection2D()

            det.bbox.center.position.x = float((x1 + x2) / 2.0)
            det.bbox.center.position.y = float((y1 + y2) / 2.0)
            det.bbox.center.theta = 0.0

            det.bbox.size_x = float(x2 - x1)
            det.bbox.size_y = float(y2 - y1)


            hyp = ObjectHypothesisWithPose()
            hyp.hypothesis.class_id = str(cls_id)
            hyp.hypothesis.score = conf
            det.results.append(hyp)

            det_arr.detections.append(det)

        self.det_pub.publish(det_arr)

        annotated_frame = results.plot()

        annotated_rgb = cv2.cvtColor(annotated_frame, cv2.COLOR_BGR2RGB)
        out_msg = self.bridge.cv2_to_imgmsg(annotated_rgb, encoding='rgb8')

        out_msg.header = msg.header
        self.pub.publish(out_msg)
        # self.get_logger().info(f"Processed image {frame.shape[1]}x{frame.shape[0]}")

def main(args=None):
    rclpy.init(args=args)
    node = YoloNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()
if __name__ == "__main__":
    main()

