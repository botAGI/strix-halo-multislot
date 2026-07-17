#!/bin/bash
# Лучший агрегат кампании: Gemma4 26B A4B QAT, 32 слота, 236 tok/s суммарно.
# Модель: unsloth/gemma-4-26B-A4B-it-qat-GGUF, файл UD-Q4_K_XL (~16 GB).
# Дистилляция: dense-attention MoE масштабируется монотонно — никаких «долин».
# ВАЖНО: без MTP-драфта. На насыщенном батче GPU compute-bound и драфт — чистый
# налог (замерено: с MTP на 32 потоках −33%). MTP — см. 04-single-user-mtp.sh.
set -e
MODELS_DIR="${MODELS_DIR:-/var/lib/agmind/models}"
IMAGE="ghcr.io/ggml-org/llama.cpp@sha256:25932f6dde7478203be75a04651d210ff1a5f0ac7877fb61f4fa622943bea6df"

docker run -d --name llm-gemma \
  --restart unless-stopped \
  --device /dev/dri \
  --group-add 44 --group-add 992 \
  -v "$MODELS_DIR":/models:ro \
  -p 8080:8080 \
  -e VK_DRIVER_FILES=/usr/share/vulkan/icd.d/radeon_icd.json \
  "$IMAGE" \
  --host 0.0.0.0 --port 8080 --metrics \
  -m /models/gemma-4-26B-A4B-it-UD-Q4_K_XL.gguf \
  -ngl 999 --flash-attn on \
  --ubatch-size 1024 --batch-size 4096 --no-mmap \
  --ctx-size 262144 --parallel 32
# 262144 / 32 = 8192 токенов контекста на слот. Нужен длиннее — уменьшайте --parallel.
# --group-add ЧИСЛОВЫМИ GID (video=44, render=992 в Ubuntu): в образе нет именованных групп.
