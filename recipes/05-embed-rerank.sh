#!/bin/bash
# RAG-обвязка на том же узле: embed 255 rps, rerank ~7 rps (насыщение).
# bge-m3 (эмбеддинги) + bge-reranker-v2-m3, оба Q8_0.
#
# Замеры --parallel (одиночные короткие тексты, 16 клиентов):
#   embed:  np4 = 194 rps | np8 = 255 | np16 = 255 (потолок)  → берите 8
#   rerank: np1 = 2.8 rps | np4 = 7.3 | np8 = 7.3 (потолок)   → берите 4
# ГРАБЛЯ: дефолт --parallel у llama-server = 4, НЕ 1. Сервер без флага уже крутит
# 4 слота — проверяйте /props → total_slots, а не список флагов.
# Rerank строго линеен по документам (~144 док/с): размер пачки влияет только на
# латентность запроса, не на суммарную пропускную.
set -e
MODELS_DIR="${MODELS_DIR:-/var/lib/agmind/models}"
IMAGE="ghcr.io/ggml-org/llama.cpp@sha256:25932f6dde7478203be75a04651d210ff1a5f0ac7877fb61f4fa622943bea6df"

docker run -d --name embed \
  --restart unless-stopped \
  --device /dev/dri --group-add 44 --group-add 992 \
  -v "$MODELS_DIR":/models:ro -p 8081:8080 \
  -e VK_DRIVER_FILES=/usr/share/vulkan/icd.d/radeon_icd.json \
  "$IMAGE" \
  --host 0.0.0.0 --port 8080 --metrics \
  -m /models/bge-m3-Q8_0.gguf \
  --embeddings --pooling cls -ngl 999 \
  --ctx-size 16384 --parallel 8
# ctx = 2048 × parallel: держим 2048 токенов на слот.

docker run -d --name rerank \
  --restart unless-stopped \
  --device /dev/dri --group-add 44 --group-add 992 \
  -v "$MODELS_DIR":/models:ro -p 8082:8080 \
  -e VK_DRIVER_FILES=/usr/share/vulkan/icd.d/radeon_icd.json \
  "$IMAGE" \
  --host 0.0.0.0 --port 8080 --metrics \
  -m /models/bge-reranker-v2-m3-Q8_0.gguf \
  --reranking --pooling rank -ngl 999 \
  --ctx-size 32768 --parallel 4
# ctx = 8192 × parallel: запрос+документ должны влезать в слот.

# ЧЕСТНОЕ ПРЕДУПРЕЖДЕНИЕ про «всё на одной коробке» (замерено):
# генерация (4 юзера, RAG-промпты ~3.4К) + embed + rerank ОДНОВРЕМЕННО работают
# стабильно, но каждый теряет 40-70% против соло. Ёмкость такой коробки —
# 2-4 одновременных RAG-юзера (TTFT ~5с). Больше — выносите генерацию на второй узел.
