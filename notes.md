Microsoft Visual Studio Community 2022 (64-bit)

# Configure with CMake (adjust Visual Studio version if needed)
cmake -G "Visual Studio 16 2019" -A x64 `
  -DCMAKE_TOOLCHAIN_FILE=C:/vcpkg/scripts/buildsystems/vcpkg.cmake `
  -DBUILD_BROWSER=OFF `
  -DCOPIED_DEPENDENCIES=false `
  -DCOPY_DEPENDENCIES=true `
  ..

# Build OBS Studio
cmake --build . --config RelWithDebInfo


Executing command: /mnt/c/code/ADRVE/adrve-edge/amazon-kinesis-video-streams-producer-sdk-cpp/build/kvs_gstreamer_sample AWS_REGION=us-west-2 STREAM_NAME=adrve-video-stream VIDEO_WIDTH=1280 VIDEO_HEIGHT=720 VIDEO_FPS=15 RETENTION_PERIOD=2
Started KVS producer with PID: 55077
Opening video device 0
KVS ERR: log4cplus:ERROR could not open file ../kvs_log_configuration
KVS ERR: log4cplus:ERROR No appenders could be found for logger (com.amazonaws.kinesis.video.gstreamer).
KVS ERR: log4cplus:ERROR Please initialize the log4cplus system properly.