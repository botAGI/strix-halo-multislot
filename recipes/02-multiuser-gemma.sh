#!/bin/bash
# Лучший агрегат кампании: Gemma4 26B A4B QAT, 32 слота, 236 tok/s суммарно
# (скрининг 75с; за 30 мин непрерывно в среднем 226).
# Модель: unsloth/gemma-4-26B-A4B-it-qat-GGUF, файл UD-Q4_K_XL (~16 GB).
# Архитектура: MoE (3.8B активных из 25.2B), softmax-внимание с чередованием
# sliding-window и global слоёв 5:1. Долина на переходе 8→10 клиентов есть и у неё
# (161,4 → 123,7, медианы 3×), но мельче, чем у Qwen, и к 14-16 клиентам полностью отыгрывается;
# дальше рост монотонный до 236 на 32 клиентах.
# ВАЖНО: без MTP-драфта. На НАШЕМ стеке (Vulkan/RADV) MTP на 32 запросах
# отнимал треть агрегата; Google для своих стеков заявляет обратное на batch
# 4-8, так что точка перегиба зависит от стека. MTP — см. 04-single-user-mtp.sh.
set -e
MODELS_DIR="${MODELS_DIR:-/var/lib/llm-models}"
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
  `# sha256 453cf049ba87a29b9ed5739087b84b7fa0265a4f2b11eefa2c77683dec6a8020` \
  -ngl 999 --flash-attn on \
  --ubatch-size 1024 --batch-size 4096 --no-mmap \
  --ctx-size 262144 --parallel 32
# 262144 / 32 = 8192 токенов контекста на слот. Нужен длиннее — уменьшайте --parallel.
# --group-add ЧИСЛОВЫМИ GID (video=44, render=992 в Ubuntu): в образе нет именованных групп.
