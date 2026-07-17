# strix-halo-multislot

**English** · [Русский](README.ru.md)

Multi-slot LLM inference recipes and honest benchmarks for AMD Strix Halo
(Ryzen AI Max+ 395, Radeon 8060S, 128 GB unified memory). One mini-PC serves 32
concurrent streams at **236 tok/s aggregate** (Gemma4 26B A4B, llama.cpp Vulkan/RADV),
sustains it for 30 minutes without throttling, and reaches **~90 tok/s single-stream**
with the built-in MTP draft. Everything here reproduces on any Strix Halo mini-PC in
an evening: launch scripts in `recipes/`, harnesses in `bench/`, full tables in `results/`.

## Headline numbers

| Scenario | Config | Result |
|---|---|---|
| Multi-user chat | Gemma4 26B A4B, `-np 32` | **236 tok/s** aggregate, 32 streams |
| Endurance | same, 30 min non-stop | **226 tok/s** average, 78°C, no throttling |
| Multi-user Qwen | Qwen3.6-35B-A3B Q4_0, `-np 32` | 181 tok/s aggregate |
| Single-user chat | Qwen3.6 UD-Q4_K_M + MTP | **~90 tok/s** per stream |
| Embed (bge-m3) | `--parallel 8` | 255 rps |
| Rerank (bge-reranker-v2-m3) | `--parallel 4+` | ~7 rps (saturated) |

Hardware: Beelink GTR9 Pro (Ryzen AI Max+ 395, Radeon 8060S gfx1151, 128 GB LPDDR5X),
Ubuntu, kernel 6.17, Mesa/RADV, llama.cpp `server-vulkan`
(`ghcr.io/ggml-org/llama.cpp@sha256:25932f6dde7478203be75a04651d210ff1a5f0ac7877fb61f4fa622943bea6df`).

## What's inside

- `recipes/01-node-tuning.md` — kernel parameters (mandatory: +7-8% generation and a
  2× larger GTT pool; without them two large models won't fit).
- `recipes/02-multiuser-gemma.sh` — best aggregate (236 tok/s).
- `recipes/03-multiuser-qwen.sh` — Qwen3.6 in multi-slot and quant choice.
- `recipes/04-single-user-mtp.sh` — single-stream maximum (built-in MTP draft).
- `recipes/05-embed-rerank.sh` — RAG side-services: embed/rerank parallelism.
- `recipes/TROUBLESHOOTING.md` — hard-won gotchas, from numeric GIDs to `-fit off`.
- `bench/` — harnesses (Python + requests, no host dependencies).
- `results/RESULTS.md` — full tables, including failures and refuted hypotheses.

## Methodology

- Unique salted prompts, `cache_prompt: false` — the cache doesn't cheat for you.
- Metrics come from server `timings`; aggregate = Σ predicted_n / makespan.
- Screening: 1×75s per config; final numbers: 3 runs, median.
- Failures are published: the Qwen valley at 16 streams, the MTP tax on batches, the
  45-second embed stalls — all in `results/`, nothing hidden.
- Load clients hit the server over the network from a neighboring node, not the box under test.

## Key findings (short)

1. **Model choice matters more than flags.** Dense-attention MoE (Gemma4) scales
   monotonically to 236; the DeltaNet hybrid (Qwen3.6) has a reproducible "valley" at
   10-20 streams and a ~180 ceiling — an architecture property, confirmed by controls.
2. **Speculative decoding (MTP) is a single-user tool.** +40% at 1 stream, +21% at 2,
   already −31% at 4 and −33% at 32 (acceptance 69-74%). Crossover is 2-3 users.
3. **Quants aren't equal under batching.** Q4_0 is fastest at 32 streams (cheap dequant),
   Q4_K_M wins single-stream. Up to 10% difference.
4. **Kernel tuning is mandatory** and buys exactly +7-8% generation (A/B with reboot,
   kernel pinned).
5. **llama-server's default `--parallel` is 4, not 1.** Compare configs by
   `/props → total_slots`, not by the flag list — we nearly "discovered" a false 2.6× effect this way.

## License

MIT
