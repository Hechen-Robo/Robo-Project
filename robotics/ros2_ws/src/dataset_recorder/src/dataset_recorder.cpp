#include <rclcpp/rclcpp.hpp>

#include <rosbag2_transport/recorder.hpp>
#include <rosbag2_transport/record_options.hpp>
#include <rosbag2_storage/storage_options.hpp>
#include <rosbag2_cpp/writer.hpp>

#include <yaml-cpp/yaml.h>

#include <chrono>
#include <csignal>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>
#include <rmw/rmw.h>

namespace fs = std::filesystem;

static std::atomic<bool> g_request_shutdown{false};

static std::string now_string()
{
  using clock = std::chrono::system_clock;
  auto t = clock::to_time_t(clock::now());
  std::tm tm{};
#ifdef _WIN32
  localtime_s(&tm, &t);
#else
  localtime_r(&t, &tm);
#endif
  std::ostringstream oss;
  oss << std::put_time(&tm, "%Y-%m-%d_%H-%M-%S");
  return oss.str();
}

static void on_signal(int)
{
  g_request_shutdown.store(true);
}

struct TopicConfig
{
  bool all{false};
  std::vector<std::string> topics;
};

static TopicConfig load_topics_yaml(const std::string &path)
{
  YAML::Node root = YAML::LoadFile(path);
  TopicConfig cfg;
  cfg.all = root["all"] ? root["all"].as<bool>() : false;

  if (!cfg.all)
  {
    if (!root["topics"] || !root["topics"].IsSequence())
    {
      throw std::runtime_error("topics.yaml missing 'topics' list while all=false");
    }
    for (const auto &n : root["topics"])
    {
      cfg.topics.push_back(n.as<std::string>());
    }
    if (cfg.topics.empty())
    {
      throw std::runtime_error("topics.yaml 'topics' is empty while all=false");
    }
  }
  return cfg;
}

static void write_manifest(
    const fs::path &session_dir,
    const std::string &session_id,
    const std::string &topics_yaml_path,
    const rosbag2_storage::StorageOptions &storage,
    const rosbag2_transport::RecordOptions &record,
    int duration_sec)
{
  std::ofstream f(session_dir / "manifest.json");
  f << "{\n";
  f << "  \"session_id\": " << "\"" << session_id << "\",\n";
  f << "  \"topics_yaml\": " << "\"" << topics_yaml_path << "\",\n";
  f << "  \"storage\": {\n";
  f << "    \"uri\": " << "\"" << storage.uri << "\",\n";
  f << "    \"storage_id\": " << "\"" << storage.storage_id << "\",\n";
  f << "    \"max_bagfile_size\": " << storage.max_bagfile_size << ",\n";
  f << "    \"max_bagfile_duration\": " << storage.max_bagfile_duration << "\n";
  f << "  },\n";
  f << "  \"record\": {\n";
  f << "    \"all\": " << (record.all ? "true" : "false") << ",\n";
  f << "    \"compression_mode\": " << "\"" << record.compression_mode << "\",\n";
  f << "    \"compression_format\": " << "\"" << record.compression_format << "\",\n";
  f << "    \"topics\": [";
  for (size_t i = 0; i < record.topics.size(); ++i)
  {
    f << "\"" << record.topics[i] << "\"";
    if (i + 1 < record.topics.size())
      f << ", ";
  }
  f << "]\n";
  f << "  },\n";
  f << "  \"auto_stop_sec\": " << duration_sec << "\n";
  f << "}\n";
}

int main(int argc, char **argv)
{
  // ----- very small arg parser -----
  std::string config_path = "topics.yaml";
  std::string out_root = "./datasets";
  std::string name_prefix = "session";
  std::string storage_id = "sqlite3";  // or "mcap"
  std::string compression_format = ""; // "zstd" / "lz4" / ""
  std::string compression_mode = "";   // "file" / "message" / ""
  uint64_t max_bagfile_size = 0;       // bytes, 0 disables
  uint64_t max_bagfile_duration = 0;   // seconds, 0 disables
  int duration_sec = -1;               // -1 means run until Ctrl+C

  for (int i = 1; i < argc; ++i)
  {
    std::string a = argv[i];
    auto need = [&](const char *key)
    {
      if (i + 1 >= argc)
      {
        throw std::runtime_error(std::string("Missing value for ") + key);
      }
      return std::string(argv[++i]);
    };

    if (a == "--config")
      config_path = need("--config");
    else if (a == "--out")
      out_root = need("--out");
    else if (a == "--name")
      name_prefix = need("--name");
    else if (a == "--storage")
      storage_id = need("--storage");
    else if (a == "--compression")
      compression_format = need("--compression");
    else if (a == "--compression-mode")
      compression_mode = need("--compression-mode");
    else if (a == "--max-bag-size")
      max_bagfile_size = std::stoull(need("--max-bag-size"));
    else if (a == "--max-bag-duration")
      max_bagfile_duration = std::stoull(need("--max-bag-duration"));
    else if (a == "--duration")
      duration_sec = std::stoi(need("--duration"));
    else if (a == "-h" || a == "--help")
    {
      std::cout << "Usage:\n"
                   "  dataset_recorder --config topics.yaml --out ./datasets --name realsense\n"
                   "                 [--storage sqlite3|mcap]\n"
                   "                 [--compression zstd|lz4] [--compression-mode file|message]\n"
                   "                 [--max-bag-size BYTES] [--max-bag-duration SECONDS]\n"
                   "                 [--duration SECONDS]\n";
      return 0;
    }
  }

  // ----- signals -----
  std::signal(SIGINT, on_signal);
  std::signal(SIGTERM, on_signal);

  // ----- load topics -----
  TopicConfig tc = load_topics_yaml(config_path);

  // ----- make session dir -----
  std::string session_id = name_prefix + "_" + now_string();
  fs::path session_dir = fs::path(out_root) / session_id;
  fs::create_directories(session_dir);

  // snapshot topics.yaml
  try
  {
    fs::copy_file(config_path, session_dir / "topics.yaml", fs::copy_options::overwrite_existing);
  }
  catch (...)
  {
    // ignore
  }

  // ----- configure rosbag2 options -----
  rosbag2_storage::StorageOptions storage;
  storage.uri = (session_dir / "bag").string();        // bag prefix path
  storage.storage_id = storage_id;                     // "sqlite3" / "mcap"
  storage.max_bagfile_size = max_bagfile_size;         // 0 disables
  storage.max_bagfile_duration = max_bagfile_duration; // 0 disables

  rosbag2_transport::RecordOptions record;
  record.all = tc.all; // RecordOptions has 'all' :contentReference[oaicite:2]{index=2}
  record.topics = tc.topics;
  record.rmw_serialization_format = rmw_get_serialization_format();
  record.compression_mode = compression_mode;     // "file"/"message"/""
  record.compression_format = compression_format; // "zstd"/"lz4"/""

  // write manifest early
  write_manifest(session_dir, session_id, config_path, storage, record, duration_sec);

  std::cout << "\n=== rosbag2 dataset recorder ===\n";
  std::cout << "Session: " << session_id << "\n";
  std::cout << "Dir:     " << session_dir << "\n";
  std::cout << "URI:     " << storage.uri << "\n";
  std::cout << "Storage: " << storage.storage_id << "\n";
  std::cout << "Topics:  " << (record.all ? std::string("* (all)") : std::to_string(record.topics.size())) << "\n";
  std::cout << "================================\n\n";

  // ----- start recorder node -----
  rclcpp::init(argc, argv);

  // Writer + Recorder (API constructor exists) :contentReference[oaicite:3]{index=3}
  auto writer = std::make_shared<rosbag2_cpp::Writer>();
  auto recorder = std::make_shared<rosbag2_transport::Recorder>(
      writer, storage, record, "dataset_recorder", rclcpp::NodeOptions());

  recorder->record(); // starts in background :contentReference[oaicite:4]{index=4}

  auto exec = std::make_shared<rclcpp::executors::SingleThreadedExecutor>();
  exec->add_node(recorder);

  auto start = std::chrono::steady_clock::now();

  while (rclcpp::ok() && !g_request_shutdown.load())
  {
    exec->spin_some();

    if (duration_sec > 0)
    {
      auto elapsed = std::chrono::duration_cast<std::chrono::seconds>(
                         std::chrono::steady_clock::now() - start)
                         .count();
      if (elapsed >= duration_sec)
      {
        std::cout << "[INFO] Duration reached, stopping...\n";
        break;
      }
    }
    std::this_thread::sleep_for(std::chrono::milliseconds(50));
  }

  // stop recording cleanly (flush buffers, close writer) :contentReference[oaicite:5]{index=5}
  try
  {
    recorder->stop();
  }
  catch (const std::exception &e)
  {
    std::cerr << "[WARN] recorder->stop() exception: " << e.what() << "\n";
  }

  rclcpp::shutdown();
  std::cout << "[INFO] Done. Output: " << session_dir << "\n";
  return 0;
}
