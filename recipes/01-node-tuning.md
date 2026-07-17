# Тюнинг узла (обязательный шаг)

Параметры ядра для Strix Halo под LLM-нагрузку. Вклад измерен A/B-экспериментом с ребутом
(единственная переменная — эти параметры; ядро при ребуте запинено):

| Замер | Без тюнинга | С тюнингом |
|---|---|---|
| Gemma4 26B, -np 32, 32 потока | 219.8 tok/s | **235.7** |
| Qwen3.6 Q4_0, -np 32, 32 потока | 167.8 | **180.9** |
| embed bge-m3, --parallel 8 | 240 rps | **255** |
| GTT-пул (память для GPU) | 62.5 GiB | **117.4 GiB** |

Без `ttm.pages_limit` GPU получает только ~50% RAM — две больших модели одновременно
(например 26B + 35B для A/B) просто не влезут.

## Параметры

В `/etc/default/grub.d/99-llm.cfg` (drop-in, не трогает основной конфиг):

```
GRUB_CMDLINE_LINUX_DEFAULT="$GRUB_CMDLINE_LINUX_DEFAULT ttm.pages_limit=30788203 ttm.page_pool_size=30788203 amd_iommu=off zswap.enabled=0"
```

Потом `sudo update-grub && sudo reboot`.

- `ttm.pages_limit` — максимум системных страниц, которые TTM отдаёт GPU. Значение =
  94% RAM в страницах: `RAM_байт × 0.94 / 4096` (для 128 GB ≈ 30788203).
- `ttm.page_pool_size` — кэш-пул WC/UC-страниц TTM, то же значение.
- `amd_iommu=off` — убирает DMA-трансляцию. Только для bare-metal узла:
  **не выключайте IOMMU, если на хосте виртуалки или PCI-passthrough.**
- `zswap.enabled=0` — GPU делит шину памяти с CPU, компрессия свопа мешает.

Опционально: `amdgpu.lockup_timeout=60000` — на непрерывном батчинге Vulkan-сабмиты
могут превышать дефолтный ~2с таймаут ядра и ловить ложный GPU-reset (llama.cpp #21724).

## Проверка после ребута

```bash
cat /proc/cmdline                                        # параметры на месте
awk '{printf "%.1f GiB\n", $1/2**30}' \
  /sys/class/drm/card*/device/mem_info_gtt_total          # ~94% RAM
```

## Грабля: пиновка ядра при A/B

Если сравниваете «до/после» ребутом — проверьте `ls /boot/vmlinuz-*`: apt мог накатить
новое ядро, и ребут молча сменит ДВЕ переменные. Пин через тот же drop-in:

```
GRUB_DEFAULT="Advanced options for Ubuntu>Ubuntu, with Linux <ваша-текущая-версия>-generic"
```
