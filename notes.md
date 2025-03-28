cMicrosoft Visual Studio Community 2022 (64-bit)

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

cmake -G "Visual Studio 17 2022" -A x64 `
  -DCMAKE_TOOLCHAIN_FILE=C:/vcpkg/scripts/buildsystems/vcpkg.cmake `
  -DDepsPath="C:/code/obs-studio/deps/windows-deps-2022-08-02-x64" `
  -DBUILD_BROWSER=OFF `
  -DCOPIED_DEPENDENCIES=false `
  -DCOPY_DEPENDENCIES=true `
  ..

cmake -G "Visual Studio 17 2022" -A x64 `
  -DCMAKE_TOOLCHAIN_FILE=C:/vcpkg/scripts/buildsystems/vcpkg.cmake `
  -DCMAKE_PREFIX_PATH="C:/vcpkg/installed/x64-windows" `
  -DBUILD_BROWSER=OFF `
  -DENABLE_BROWSER=OFF `
  -DENABLE_UPDATER=OFF `
  -DCOPY_DEPENDENCIES=ON `
  ..


  cmake -G "Visual Studio 17 2022" -A x64 `
  -DCMAKE_TOOLCHAIN_FILE=C:/vcpkg/scripts/buildsystems/vcpkg.cmake `
  -DCMAKE_PREFIX_PATH="C:/vcpkg/installed/x64-windows" `
  -DBUILD_BROWSER=OFF `
  -DENABLE_BROWSER=OFF `
  -DENABLE_UPDATER=OFF `
  -DQTDIR="C:/vcpkg/installed/x64-windows" `
  -DQT_VERSION=5 `
  ..

  cmake -G "Visual Studio 17 2022" -A x64 `
  -DCMAKE_TOOLCHAIN_FILE=C:/vcpkg/scripts/buildsystems/vcpkg.cmake `
  -DCMAKE_PREFIX_PATH="C:/vcpkg/installed/x64-windows" `
  -DDISABLE_UI=ON `
  -DENABLE_BROWSER=OFF `
  -DENABLE_UPDATER=OFF `
  ..