# strix-halo-multislot

**EN TL;DR.** Multi-slot LLM inference recipes and honest benchmarks for AMD Strix Halo
(Ryzen AI Max+ 395, Radeon 8060S, 128 GB unified memory). One mini-PC serves 32 concurrent
streams at **236 tok/s aggregate** (Gemma4 26B A4B, llama.cpp Vulkan/RADV), sustains it for
30 minutes without throttling, and hits **~90 tok/s single-stream** with the built-in MTP
draft. Every number below was measured with the harnesses in `bench/`, failures included.

Рецепты мультислот-инференса и честные бенчи на AMD Strix Halo. Всё, что здесь есть,
воспроизводится на любом Strix Halo мини-ПК за вечер: скрипты запуска в `recipes/`,
харнессы в `bench/`, полные таблицы в `results/`.

## Главные числа

| Сценарий | Конфиг | Результат |
|---|---|---|
| Мультиюзер-чат | Gemma4 26B A4B, `-np 32` | **236 tok/s** агрегат, 32 потока |
| Выносливость | то же, 30 мин непрерывно | **226 tok/s** средний, 78°C, без троттлинга |
| Мультиюзер Qwen | Qwen3.6-35B-A3B Q4_0, `-np 32` | 181 tok/s агрегат |
| Одиночный чат | Qwen3.6 UD-Q4_K_M + MTP | **~90 tok/s** на поток |
| Embed (bge-m3) | `--parallel 8` | 255 rps |
| Rerank (bge-reranker-v2-m3) | `--parallel 4+` | ~7 rps (насыщение) |

Железо: Beelink GTR9 Pro (Ryzen AI Max+ 395, Radeon 8060S gfx1151, 128 GB LPDDR5X),
Ubuntu, ядро 6.17, Mesa/RADV, llama.cpp `server-vulkan`
(`ghcr.io/ggml-org/llama.cpp@sha256:25932f6dde7478203be75a04651d210ff1a5f0ac7877fb61f4fa622943bea6df`).

## Что внутри

- `recipes/01-node-tuning.md` — параметры ядра (обязательны: +7-8% генерации и вдвое
  больший GTT-пул; без них две больших модели не влезут).
- `recipes/02-multiuser-gemma.sh` — лучший агрегат (236 tok/s).
- `recipes/03-multiuser-qwen.sh` — Qwen3.6 в мультислоте и выбор кванта.
- `recipes/04-single-user-mtp.sh` — максимум одного потока (встроенный MTP-драфт).
- `recipes/05-embed-rerank.sh` — RAG-обвязка: embed/rerank параллелизация.
- `recipes/TROUBLESHOOTING.md` — грабли, собранные лбом: от численных GID до `-fit off`.
- `bench/` — харнессы (Python + requests, без зависимостей от железа).
- `results/RESULTS.md` — полные таблицы, включая провалы и опровергнутые гипотезы.

## Методология

- Уникальные промпты с солью, `cache_prompt: false` — кэш не подыгрывает.
- Источник метрик — серверные `timings`; агрегат = Σ predicted_n / makespan.
- Скрининг: 1×75с на конфиг; финальные числа: 3 прогона, медиана.
- Провалы публикуются: долина Qwen на 16 потоках, MTP-налог на батче, 45-секундные
  столлы embed — всё в `results/`, ничего не спрятано.
- Нагрузочные клиенты бьют по сети с соседнего узла, не с тестируемой машины.

## Ключевые находки (кратко)

1. **Выбор модели решает больше флагов.** Dense-attention MoE (Gemma4) масштабируется
   монотонно до 236; гибрид DeltaNet (Qwen3.6) имеет воспроизводимую «долину» на 10-20
   потоках и потолок ~180 — это свойство архитектуры, подтверждено контролями.
2. **Спекулятивный декодинг (MTP) — инструмент одного юзера.** +40% на 1 потоке,
   +21% на 2, уже −31% на 4 и −33% на 32 (acceptance 69-74%). Точка переключения — 2-3 юзера.
3. **Кванты не равны под батчем.** Q4_0 быстрее всех на 32 потоках (простой dequant),
   Q4_K_M — на одиночном. Разница до 10%.
4. **Тюнинг ядра обязателен** и стоит ровно +7-8% генерации (A/B с ребутом, ядро запинено).
5. **Дефолт `--parallel` у llama-server = 4, а не 1.** Сравнивайте конфиги по
   `/props → total_slots`, не по списку флагов — мы на этом чуть не «открыли» ложный эффект 2.6×.

## Лицензия

MIT
