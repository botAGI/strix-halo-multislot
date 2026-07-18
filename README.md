# strix-halo-multislot

**English** · [Русский](README.ru.md)

Multi-slot LLM inference recipes and benchmarks for AMD Strix Halo
(Ryzen AI Max+ 395, Radeon 8060S, 128 GB unified memory). One mini-PC reaches
**236 tok/s aggregate over 32 concurrent requests** in 75-second screening runs
(~7 tok/s per request) and **averages 226 tok/s over a 30-minute sustained run**
at 78°C with no throttling. With the built-in MTP draft a single stream reaches
**~90 tok/s**. The procedure reproduces in an evening on a comparable Strix Halo with sufficient memory:
launch scripts in `recipes/`, harnesses in `bench/`, tables in `results/`,
per-run values for key and final runs in `results/raw/`.

All numbers are measurements of THIS testbed (llama.cpp Vulkan/RADV, pinned
image digest). Where a result may not generalize, the tables say so.

## Headline numbers

| Scenario | Config | Result |
|---|---|---|
| Multi-user chat, screening | Gemma 4 26B A4B, `-np 32`, 32 clients | **236 tok/s** aggregate (75s runs; run-to-run spread 235–246), ~7 tok/s per request |
| Endurance | same, 30 min non-stop, 32 clients | **226 tok/s** average, 78°C, no throttling, 1.4% responses without `timings` counted as errors |
| Multi-user Qwen | Qwen3.6-35B-A3B Q4_0, `-np 32` | 178 tok/s aggregate (median of 3) |
| Single-user chat | Qwen3.6 UD-Q4_K_M + MTP | **~90 tok/s** per stream (median of 3) |
| Embed (bge-m3) | `--parallel 8` | 255 rps |
| Rerank (bge-reranker-v2-m3) | 4+ slots | ~7 rps (saturated) |

Hardware: Beelink GTR9 Pro (Ryzen AI Max+ 395, Radeon 8060S gfx1151, 128 GB LPDDR5X),
Ubuntu, kernel 6.17, Mesa/RADV, llama.cpp `server-vulkan`
(`ghcr.io/ggml-org/llama.cpp@sha256:25932f6dde7478203be75a04651d210ff1a5f0ac7877fb61f4fa622943bea6df`;
some early runs used the b9049 pin, tables mark which).

## What's inside

- `recipes/01-node-tuning.md` — kernel parameters: the 4-parameter set bought +7-8%
  generation and a 2× larger GTT pool in a reboot A/B; read the caveats before applying.
- `recipes/02-multiuser-gemma.sh` — best aggregate (236 tok/s screening / 226 sustained).
- `recipes/03-multiuser-qwen.sh` — Qwen3.6 in multi-slot and quant choice.
- `recipes/04-single-user-mtp.sh` — single-stream maximum (built-in MTP draft).
- `recipes/05-embed-rerank.sh` — RAG side-services: embed/rerank parallelism.
- `recipes/TROUBLESHOOTING.md` — hard-won gotchas, from numeric GIDs to `-fit off`.
- `bench/` — harnesses (Python + requests, no host dependencies).
- `results/RESULTS.md` — full tables, including failures and refuted hypotheses.
- `results/raw/` — per-run values, per-minute sustained series, GPU telemetry.

## Methodology

- Unique salted prompts, `cache_prompt: false` — the cache doesn't cheat for you.
- Metrics come from server `timings`; aggregate = Σ predicted_n / makespan.
  Note: `timings.prompt_ms` is server-side prompt processing time (queue wait
  excluded); we label it as such, not as client TTFT.
- Screening: 1×75s per config. Final numbers: 3 runs, median (tables mark the
  exceptions where fewer runs exist).
- Load clients hit the server over the network from a neighboring node.
- Failures and refuted hypotheses are published in `results/RESULTS.md`, section 10 —
  including three of our own claims that better measurements later overturned.

## Key findings (short, testbed-scoped)

1. **The 8→10 concurrency cliff is stack-wide, not model-specific.** Both
   architectures and all three quants dip right after 8 concurrent requests
   (Gemma 158.7→123.7, Qwen Q4_K_M 149→99). The model sets the depth (−22%…−34%),
   the recovery (Gemma is back by 14–16 clients and climbs to 236; Qwen crawls to a
   160–178 ceiling) and therefore still decides your throughput. Root cause not
   established — we did not profile the kernels. The cure is model-specific: capping
   Qwen at ≤8 active requests per process is measured to help; Gemma recovers on its
   own and a cap would cost her the 236 ceiling.
2. **On this stack, speculative decoding (MTP) won at the measured points of
   1 and 2 clients and lost at 4, 8 and 32:** +42%/+21% vs −31%/−25%/−33%
   (acceptance 69–74%; intermediate levels not measured). Google's own
   materials report ~2.2× MTP speedups at batch 4-8 on Apple Silicon and similar
   gains on A100, so treat the crossover as stack-dependent, not universal.
3. **Quants aren't equal.** On the tuned testbed Q4_0 led at every concurrency
   level, up to 11% at batch (medians of 3 runs). Early single runs on the untuned
   node suggested Q4_K_M wins single-stream; repeats overturned that. Quality was
   not evaluated — measure it before picking a production quant.
4. **The kernel-tuning set (4 parameters together) bought +7-8% generation** in a
   reboot A/B with the kernel pinned. Per-parameter contributions were not isolated.
5. **`--parallel` defaults to -1 (auto); in current server.cpp sources auto is
   hardcoded to 4 slots** (verified on both our images; may change in any build). A server started without the flag is
   already multi-slot. Compare configs by `/props → total_slots`, not by flag lists —
   this mistake almost led us to publish a false 2.6× "finding".

## License

MIT
