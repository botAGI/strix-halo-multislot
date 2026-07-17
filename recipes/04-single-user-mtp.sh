#!/bin/bash
# Максимум одиночного потока: ~90 tok/s (Qwen3.6-35B-A3B + встроенная MTP-голова).
# Модель: unsloth/Qwen3.6-35B-A3B-MTP-GGUF (кванты с СОХРАНЁННОЙ MTP-головой,
# отдельный драфт-файл не нужен). Обычные GGUF-конверсии голову теряют.
#
# КОГДА ВКЛЮЧАТЬ MTP НА ЭТОМ СТЕКЕ (замерено на Strix Halo + Vulkan/RADV,
# acceptance 69-74% на смешанных задачах):
#   1 поток: +40%  |  2 потока: +21%  |  4 потока: −31%  |  32 потока: −33%
# Правило ДЛЯ ЭТОГО стенда: 1-2 клиента — ON, больше — OFF.
# ВАЖНО: официальные материалы Google заявляют ~2.2x ускорения от MTP на batch
# 4-8 (Apple Silicon, 26B MoE) и сопоставимые эффекты на A100 — точка перегиба
# зависит от железа и реализации. Меряйте на своём стеке, прежде чем включать.
#
# `-fit off` ОБЯЗАТЕЛЕН: memory-fitting падает на MTP-драфтах
# («failed to measure draft model memory», llama.cpp issue #24350).
# np>1 с MTP не поддерживается (README unsloth).
set -e
MODELS_DIR="${MODELS_DIR:-/var/lib/agmind/models}"
IMAGE="ghcr.io/ggml-org/llama.cpp@sha256:25932f6dde7478203be75a04651d210ff1a5f0ac7877fb61f4fa622943bea6df"

docker run -d --name llm-single \
  --restart unless-stopped \
  --device /dev/dri \
  --group-add 44 --group-add 992 \
  -v "$MODELS_DIR":/models:ro \
  -p 8080:8080 \
  -e VK_DRIVER_FILES=/usr/share/vulkan/icd.d/radeon_icd.json \
  "$IMAGE" \
  --host 0.0.0.0 --port 8080 --metrics \
  -m /models/Qwen3.6-35B-A3B-UD-Q4_K_M.gguf \
  -ngl 999 --flash-attn on \
  --cache-type-k q8_0 --cache-type-v q8_0 --no-mmap \
  --ctx-size 65536 --parallel 1 \
  --spec-type draft-mtp --spec-draft-n-max 2 -fit off
# Проверка, что драфт реально работает: в ответе /completion поле timings должно
# содержать draft_n и draft_n_accepted > 0. ВНИМАНИЕ: /props при этом может врать
# ("speculative.types":"none") — верьте timings.
