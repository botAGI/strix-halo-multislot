#!/bin/bash
# RAG-обвязка на том же узле: embed 255 rps, rerank ~7 rps (насыщение).
# bge-m3 (эмбеддинги) + bge-reranker-v2-m3, оба Q8_0.
#
# Замеры --parallel (одиночные короткие тексты, 16 клиентов):
#   embed:  np4 = 194 rps | np8 = 255 | np16 = 242 до тюнинга, рост нулевой → берите 8
#   rerank: np1 = 2.8 rps | np4 = 7.3 | np8 = 7.3 (потолок)   → берите 4
# ГРАБЛЯ: дефолт --parallel у llama-server равен -1 (auto); в текущих исходниках
# server.cpp auto захардкожен в 4 слота (может смениться в любой сборке). Сервер
# без флага уже мультислотный — проверяйте /props → total_slots, а не список флагов.
# Rerank держит постоянные ~143-144 док/с на трёх проверенных пачках (10/20/40):
# размер пачки влияет на латентность запроса, не на суммарную пропускную.
set -e
MODELS_DIR="${MODELS_DIR:-/var/lib/llm-models}"
IMAGE="ghcr.io/ggml-org/llama.cpp@sha256:25932f6dde7478203be75a04651d210ff1a5f0ac7877fb61f4fa622943bea6df"

docker run -d --name embed \
  --restart unless-stopped \
  --device /dev/dri --group-add 44 --group-add 992 \
  -v "$MODELS_DIR":/models:ro -p 8081:8080 \
  -e VK_DRIVER_FILES=/usr/share/vulkan/icd.d/radeon_icd.json \
  "$IMAGE" \
  --host 0.0.0.0 --port 8080 --metrics \
  -m /models/bge-m3-Q8_0.gguf \
  `# sha256 6fae7a1e5c8039c7aff595830fc7b5551b4426bc679f5e526f737e2f63811afa` \
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
  `# sha256 a43c7c9b11a4c1517e5bf95151960e1621d1b72f7a493364b01e386cf1aaa1d3` \
  --reranking --pooling rank -ngl 999 \
  --ctx-size 32768 --parallel 4
# ctx = 8192 × parallel: запрос+документ должны влезать в слот.

# ЧЕСТНОЕ ПРЕДУПРЕЖДЕНИЕ про «всё на одной коробке» (замерено):
# генерация (4 юзера, RAG-промпты ~3.4К) + embed + rerank ОДНОВРЕМЕННО работают
# стабильно, но каждый теряет 40-70% против соло. Ёмкость такой коробки —
# 2-4 одновременных RAG-клиента (серверная обработка промпта ~5с в нетюненном
# нестриминговом тесте; клиентский TTFT в этом режиме не мерился).
# Больше клиентов — выносите генерацию на второй узел.
