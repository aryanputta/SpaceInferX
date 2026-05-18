"""
Kernel-level TCP BER sweep using iperf3 + macOS dummynet (dnctl/pfctl).

Captures real TCP congestion control behavior: retransmit timeouts,
window scaling, SACK, and throughput collapse under burst packet loss.

Requires sudo:
    sudo python3 experiments/tcp_characterization/run_kernel_sweep.py

Each BER point:
  1. Converts BER → per-packet loss rate (PLR) for 64KB segments
  2. Applies PLR via dummynet pipe (kernel-level drop)
  3. Runs iperf3 client/server for DURATION_S seconds
  4. Parses iperf3 JSON output for throughput, retransmits, RTT
"""

import json
import math
import os
import subprocess
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from src.networking.dummynet_emulator import DummynetConfig, DummynetEmulator, ber_to_plr

BER_SWEEP    = [0, 1e-8, 1e-7, 1e-6, 1e-5, 5e-5, 1e-4, 5e-4, 1e-3]
DURATION_S   = 15
PORT         = 15001
OUTPUT_FILE  = "results/space_analog/tcp_kernel_sweep.json"
PAYLOAD_BYTES = 65536   # 64KB — iperf3 default segment


def run_iperf_server(port: int, stop_event: threading.Event):
    proc = subprocess.Popen(
        ["iperf3", "-s", "-p", str(port), "--one-off"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    stop_event.wait()
    proc.terminate()


def run_iperf_client(port: int, duration: int) -> dict:
    result = subprocess.run(
        ["iperf3", "-c", "127.0.0.1", "-p", str(port),
         "-t", str(duration), "-J",          # JSON output
         "--length", str(PAYLOAD_BYTES),      # segment size
         "--omit", "1"],                      # skip first second (TCP warmup)
        capture_output=True, text=True, timeout=duration + 10
    )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"error": result.stderr.strip()}


def parse_iperf_result(data: dict) -> dict:
    if "error" in data:
        return {"error": data["error"]}
    try:
        end = data["end"]
        sent = end["sum_sent"]
        recv = end.get("sum_received", sent)
        streams = end.get("streams", [])
        rtts = [s["sender"].get("mean_rtt", 0) for s in streams if "sender" in s]
        mean_rtt = sum(rtts) / len(rtts) if rtts else 0
        retransmits = sum(s["sender"].get("retransmits", 0) for s in streams if "sender" in s)
        return {
            "throughput_mbps": recv.get("bits_per_second", 0) / 1e6,
            "retransmits":     retransmits,
            "mean_rtt_ms":     mean_rtt / 1000.0,   # us → ms
            "bytes_sent":      sent.get("bytes", 0),
            "bytes_recv":      recv.get("bytes", 0),
        }
    except (KeyError, ZeroDivisionError) as e:
        return {"error": str(e)}


def main():
    if os.geteuid() != 0:
        print("ERROR: this script requires sudo (dnctl/pfctl need root).")
        print("Run: sudo python3 experiments/tcp_characterization/run_kernel_sweep.py")
        sys.exit(1)

    os.makedirs("results/space_analog", exist_ok=True)
    results = []

    for ber in BER_SWEEP:
        plr = ber_to_plr(ber, PAYLOAD_BYTES)
        print(f"[kernel] BER={ber:.0e}  PLR={plr:.4f} ...", flush=True)

        cfg = DummynetConfig(
            bandwidth_mbps=100.0,
            delay_ms=20.0,
            plr=plr,
            port=PORT,
        )

        stop_event = threading.Event()
        server_thread = threading.Thread(
            target=run_iperf_server, args=(PORT, stop_event), daemon=True
        )
        server_thread.start()
        time.sleep(0.5)   # let server bind

        try:
            with DummynetEmulator(cfg):
                iperf_data = run_iperf_client(PORT, DURATION_S)
        except Exception as e:
            iperf_data = {"error": str(e)}
        finally:
            stop_event.set()
            server_thread.join(timeout=3)

        parsed = parse_iperf_result(iperf_data)
        entry = {"ber": ber, "plr": plr, **parsed}
        results.append(entry)

        if "error" not in parsed:
            print(f"  throughput={parsed['throughput_mbps']:.2f} Mbps  "
                  f"retransmits={parsed['retransmits']}  "
                  f"rtt={parsed['mean_rtt_ms']:.2f}ms")
        else:
            print(f"  ERROR: {parsed['error']}")

        time.sleep(1)   # let sockets fully close

    with open(OUTPUT_FILE, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
