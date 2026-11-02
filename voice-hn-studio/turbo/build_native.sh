#!/usr/bin/env bash
set -euo pipefail
export PATH="$HOME/.cargo/bin:$PATH"
git clone --depth=1 --recurse-submodules --shallow-submodules https://github.com/dduongtrandai/VieNeu-TTS.cpp.git cpp
python3 voice-hn-studio/turbo/make_turbo_app.py ios
cat >> cpp/CMakeLists.txt <<'EOF'
add_library(hn-turbo STATIC src/vieneu/vieneu_tts.cpp ../ios/TurboBridge.cpp)
target_include_directories(hn-turbo PRIVATE src/vieneu src ../ios/Native/include)
target_link_libraries(hn-turbo PRIVATE vieneu-tts-core)
EOF
ORT="$(pwd)/ios/Pods/onnxruntime-c/onnxruntime.xcframework/ios-arm64/onnxruntime.framework"
test -s "$ORT/onnxruntime"
mkdir -p ort-ios/include ort-ios/lib
cp -R "$ORT/Headers/." ort-ios/include/
cp "$ORT/onnxruntime" ort-ios/lib/libonnxruntime.a
cmake -S cpp -B cpp/build-ios -G Xcode \
  -DCMAKE_SYSTEM_NAME=iOS \
  -DCMAKE_OSX_SYSROOT=iphoneos \
  -DCMAKE_OSX_ARCHITECTURES=arm64 \
  -DCMAKE_OSX_DEPLOYMENT_TARGET=16.0 \
  -DCMAKE_FIND_ROOT_PATH_MODE_INCLUDE=NEVER \
  -DCMAKE_FIND_ROOT_PATH_MODE_LIBRARY=NEVER \
  -DCMAKE_XCODE_ATTRIBUTE_CODE_SIGNING_ALLOWED=NO \
  -DCMAKE_XCODE_ATTRIBUTE_CODE_SIGN_IDENTITY="" \
  -DVIENEU_NATIVE_BACKEND=cpu \
  -DVIENEU_PORTABLE_CPU=ON \
  -DGGML_BLAS=ON \
  -DBUILD_SHARED_LIBS=OFF \
  -DGGML_BACKEND_DL=OFF \
  -DONNXRUNTIME_ROOT="$(pwd)/ort-ios" \
  -DBUILD_TESTING=OFF
cmake --build cpp/build-ios --config Release --target hn-turbo --parallel 4 -- CODE_SIGNING_ALLOWED=NO
mkdir -p ios/Native/lib
python3 - <<'PY'
from pathlib import Path
import shutil
needed={"libhn-turbo.a","libvieneu-tts-core.a","libllama.a",
        "libggml.a","libggml-base.a","libggml-cpu.a","libggml-blas.a"}
found={}
for p in Path("cpp/build-ios").rglob("*.a"):
    if p.name in needed: found[p.name]=p
print("FOUND STATIC LIBRARIES:")
for k,v in found.items(): print(k, v, v.stat().st_size,flush=True)
if needed-set(found): raise RuntimeError("Missing Turbo static libraries: "+repr(needed-set(found)))
for k,v in found.items(): shutil.copyfile(v,Path("ios/Native/lib")/k)
PY
