#!/bin/bash
# Qwen3.6-35B-A3B в мультислоте: 181 tok/s агрегат на 32 потоках (тюненный узел).
# КВАНТ ИМЕЕТ ЗНАЧЕНИЕ под батчем (замеры на 32 потоках):
#   Q4_0   167.8→181  — лучший в мультислоте (простой дешёвый dequant)
#   IQ4_NL 159.3      — середина
#   Q4_K_M 152.8      — лучший на ОДИНОЧНОМ потоке (74.4 против 70.5 у Q4_0)
# ОСОБЕННОСТЬ АРХИТЕКТУРЫ (гибрид DeltaNet): воспроизводимая «долина» агрегата на
# 10-20 одновременных потоках (обрыв со 152 до ~100 при переходе 8→10) и потолок ~180.
# Это свойство модели, не билда и не флагов — dense-модель (Gemma) на том же стенде
# долины не имеет. Если ваша нагрузка живёт в зоне 10-20 потоков: либо Gemma,
# либо два сервера по -np 8 (для Q4_K_M это дало +38% на 16 потоках; Q4_0 — не даёт).
set -e
MODELS_DIR="${MODELS_DIR:-/var/lib/agmind/models}"
IMAGE="ghcr.io/ggml-org/llama.cpp@sha256:25932f6dde7478203be75a04651d210ff1a5f0ac7877fb61f4fa622943bea6df"

docker run -d --name llm-qwen \
  --restart unless-stopped \
  --device /dev/dri \
  --group-add 44 --group-add 992 \
  -v "$MODELS_DIR":/models:ro \
  -p 8080:8080 \
  -e VK_DRIVER_FILES=/usr/share/vulkan/icd.d/radeon_icd.json \
  "$IMAGE" \
  --host 0.0.0.0 --port 8080 --metrics \
  -m /models/Qwen3.6-35B-A3B-Q4_0.gguf \
  -ngl 999 --flash-attn on \
  --cache-type-k q8_0 --cache-type-v q8_0 \
  --ubatch-size 2048 --batch-size 2048 --no-mmap \
  --ctx-size 262144 --parallel 32
# q8_0 KV: вдвое меньше памяти под KV-кэш, штраф ~2% против f16 — на 32 слотах того стоит.
