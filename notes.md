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


  ./run_fixed.sh --video-file 1test0.mkv --profile org-master --no-display

  . run_video_file.sh --profile org-master --video-file 1test0.mkv --no-display


  KVS ERR: 0:00:01.711520897  8290 0x55b4a1ccade0 WARN      matroskareadcommon matroska-read-common.c:759:gst_matroska_read_common_parse_skip:<matroskademux0:sink> Unknown CueTrackPositions subelement 0xf0 - ignoring
KVS ERR: 0:00:01.711522750  8290 0x55b4a1ccade0 WARN      matroskareadcommon matroska-read-common.c:759:gst_matroska_read_common_parse_skip:<matroskademux0:sink> Unknown CueTrackPositions subelement 0xf0 - ignoring
KVS ERR: 0:00:01.711524573  8290 0x55b4a1ccade0 WARN      matroskareadcommon matroska-read-common.c:759:gst_matroska_read_common_parse_skip:<matroskademux0:sink> Unknown CueTrackPositions subelement 0xf0 - ignoring
KVS ERR: 0:00:01.711526420  8290 0x55b4a1ccade0 WARN      matroskareadcommon matroska-read-common.c:759:gst_matroska_read_common_parse_skip:<matroskademux0:sink> Unknown CueTrackPositions subelement 0xf0 - ignoring
KVS ERR: 0:00:01.711528232  8290 0x55b4a1ccade0 WARN      matroskareadcommon matroska-read-common.c:759:gst_matroska_read_common_parse_skip:<matroskademux0:sink> Unknown CueTrackPositions subelement 0xf0 - ignoring
KVS ERR: 0:00:01.711530059  8290 0x55b4a1ccade0 WARN      matroskareadcommon matroska-read-common.c:759:gst_matroska_read_common_parse_skip:<matroskademux0:sink> Unknown CueTrackPositions subelement 0xf0 - ignoring
KVS ERR: 0:00:01.711531941  8290 0x55b4a1ccade0 WARN      matroskareadcommon matroska-read-common.c:759:gst_matroska_read_common_parse_skip:<matroskademux0:sink> Unknown CueTrackPositions subelement 0xf0 - ignoring
KVS ERR: 0:00:01.711533778  8290 0x55b4a1ccade0 WARN      matroskareadcommon matroska-read-common.c:759:gst_matroska_read_common_parse_skip:<matroskademux0:sink> Unknown CueTrackPositions subelement 0xf0 - ignoring
KVS ERR: 0:00:01.747403470  8290 0x55b4a1d14a30 WARN                     bin gstbin.c:2762:gst_bin_do_latency_func:<pipeline0> did not really configure latency of 0:00:00.000000000 
KVS ERR: 0:00:01.755297056  8290 0x55b4a1d14a30 WARN                     bin gstbin.c:2762:gst_bin_do_latency_func:<pipeline0> did not really configure latency of 0:00:00.000000000 
KVS ERR: 0:00:01.755406176  8290 0x55b4a1d14a30 WARN                     bin gstbin.c:2762:gst_bin_do_latency_func:<pipeline0> did not really configure latency of 0:00:00.000000000 




                                      adrve-frame-processor-container
aws lambda get-policy --function-name adrve-frame-processor-container --profile org-master


./run_fixed.sh --video-file "/mnt/c/code/ADRVE/ADRVE/test-videos/1test0.mkv" --profile org-master --no-display