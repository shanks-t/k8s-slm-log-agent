Option 1: Build from Source (Recommended for Best Performance)

  ssh node2

  # Install dependencies
  sudo apt update
  sudo apt install -y build-essential cmake git

  # Clone llama.cpp
  git clone https://github.com/ggerganov/llama.cpp.git
  cd llama.cpp

  # Build with AVX-512 and native optimizations
  cmake -B build \
    -DGGML_NATIVE=ON \
    -DGGML_AVX512=ON \
    -DGGML_AVX2=ON \
    -DGGML_FMA=ON \
    -DCMAKE_BUILD_TYPE=Release

  # Compile (use all 12 cores)
  cmake --build build --config Release -j 12

  # Binaries in build/bin/
  cd build/bin

  What these flags do:
  - GGML_NATIVE=ON - Optimizes for your specific CPU architecture
  - GGML_AVX512=ON - Enables AVX-512 instructions (2-3x faster matrix ops)
  - GGML_AVX2=ON - Enables AVX2 (fallback if AVX-512 not available)
  - GGML_FMA=ON - Enables Fused Multiply-Add for faster math
  
### Step 2: Test with Llama 3.2 1B (Quick Baseline)

  cd ~/llama.cpp/build/bin

    # Test with 1B model first (faster download, quick test)
  ./llama-cli \
    --hf-repo hugging-quants/Llama-3.2-1B-Instruct-Q8_0-GGUF \
    --hf-file llama-3.2-1b-instruct-q8_0.gguf \
    -p "The meaning to life and the universe is" \
    --threads 16 \
    -n 128 \
    -t 16
    
## speed test on hardware
@
./llama-bench \
-m /home/trey/.cache/llama.cpp/bartowski_Llama-3.2-3B-Instruct-GGUF_Llama-3.2
-3B-Instruct-Q4_K_M.gguf \
-t 16