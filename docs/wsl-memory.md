# WSL2 Memory Issue — Diagnosis & Fix

## Symptom

WSL2 (running VS Code's Remote-WSL server) was crashing/freezing intermittently during normal dev work (VS Code + extensions + a Docker Compose stack + one or more Claude Code CLI sessions).

## Root cause

The Windows host has ~7.9 GB of total physical RAM. With no `.wslconfig` present, WSL2 fell back to its default memory cap of 50% of host RAM — **3.8 GB** — for the entire Linux VM. That ceiling, combined with only 1 GB of swap, left almost no headroom for a typical working set:

| id | process group                                              | approx. RAM |
| -- | ---------------------------------------------------------- | ----------- |
| 01 | VS Code server + extension host                            | ~460 MB     |
| 02 | Pylance                                                    | ~300 MB     |
| 03 | Claude Code CLI (x2 concurrent sessions)                   | ~420 MB     |
| 04 | GitHub Copilot                                             | ~140 MB     |
| 05 | Docker stack (Spark master + 2 workers, Jupyter, Postgres) | ~555 MB     |

At the point of diagnosis, `free -h` showed 3.0 GB used out of 3.8 GB total, with only **76 MB free** and swap already 279 MB into its 1 GB ceiling.

### Diagnostic evidence

- `dmesg` / `journalctl -k` showed **no OOM-killer events** for the current boot — so the kernel wasn't hard-killing processes. The "crashes" were closer to freezes under memory pressure than clean kills.
- `dmesg` showed **272 repeated errors** of the form:
  ```
  WSL (nnnnn - Relay) ERROR: UtilAcceptVsock:246: Waiting for abnormally long accept(11)
  ```
  recurring roughly every 60s across 8 relay handles — consistent with the WSL utility VM struggling to service VS Code's Remote-WSL port-forwarding/terminal connections while under resource pressure.
- Load average showed a recent spike (15-min average higher than 1-min), and uptime was short — consistent with a recent unplanned restart.

## Fix applied

Created `C:\Users\Admin\.wslconfig` (none existed previously) to raise the memory and swap ceilings explicitly, rather than relying on the 50%-of-host default:

```ini
[wsl2]
memory=5GB
swap=4GB
```

Applied by running `wsl --shutdown` from Windows PowerShell (not from inside the WSL session itself — doing so from within WSL would sever the very session/VS Code window issuing the command) and reopening the WSL terminal / VS Code Remote-WSL window.

## Result (post-restart verification)

| id | metric                       | before             | after               |
| -- | ---------------------------- | ------------------ | ------------------- |
| 01 | WSL2 total RAM               | 3.8 GB             | 4.8 GB (see note 1) |
| 02 | Swap                         | 1 GB (279 MB used) | 4 GB (0 B used)     |
| 03 | Available memory             | 786 MB             | 2.3 GB              |
| 04 | Relay accept errors (note 2) | 272 and climbing   | 0                   |
| 05 | OOM events                   | none (but tight)   | none                |

1. 4.8 GB reflects the 5 GB `.wslconfig` setting minus ~200 MB kernel overhead.
2. Full message: `WSL (nnnnn - Relay) ERROR: UtilAcceptVsock:246: Waiting for abnormally long accept(11)`.

## What "swap" is doing here

Swap is disk space used as overflow for RAM: when physical memory fills up, the kernel writes out inactive memory pages to disk to free RAM for active work, and reads them back in if needed later. It's a safety valve, not a performance feature — disk is far slower than RAM, so heavy swapping ("thrashing") causes sluggishness. Without enough swap, the kernel's OOM-killer instead forcibly kills a process when RAM is exhausted, which is more abrupt. Raising swap from 1 GB to 4 GB gives the system a much bigger cushion before either thrashing badly or triggering an OOM kill.

## Notes / follow-up

- The Windows host only has ~8 GB total RAM, so there's a ceiling on how far this lever can be pushed — `memory=5GB` still leaves Windows itself ~3 GB.
- Docker Compose stack (Spark master + 2 workers, Jupyter, Postgres) should be stopped (`docker compose down`) when not actively in use rather than left running for the whole session — the two idle Spark workers alone reserve meaningful JVM headroom.
- Avoid running multiple concurrent Claude Code CLI sessions in the same low-memory window; each instance costs ~200 MB.
- If `free -h` still trends toward zero `available` during normal work after this change, the next lever is reducing what runs concurrently (e.g., one Spark worker instead of two) rather than raising the WSL memory cap further, since host RAM is the hard limit.
