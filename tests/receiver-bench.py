#!/usr/bin/env python3
#
# Copyright (c) 2021 Hans Baier <hansfbaier@gmail.com>
# SPDX-License-Identifier: CERN-OHL-W-2.0
#
import sys
sys.path.append(".")

from amaranth.sim import Simulator, Tick

from adat.receiver    import ADATReceiver
from adat.nrzidecoder import NRZIDecoder
from testdata         import one_empty_adat_frame, \
                        sixteen_frames_with_channel_num_msb_and_sample_num, \
                        encode_nrzi

def test_with_samplerate(samplerate: int=48000):
    """run adat signal simulation with the given samplerate"""
    # 24 bit plus the 6 nibble separator bits for eight channel
    # then 1 separator, 10 sync bits (zero), 1 separator and 4 user bits

    clk_freq = 100e6
    dut = ADATReceiver(clk_freq)
    adat_freq = NRZIDecoder.adat_freq(samplerate)
    clockratio = clk_freq / adat_freq

    sim = Simulator(dut)
    sim.add_clock(1.0/clk_freq, domain="sync")
    sim.add_clock(1.0/adat_freq, domain="adat")

    sixteen_adat_frames = sixteen_frames_with_channel_num_msb_and_sample_num()
    testdata = \
        one_empty_adat_frame() + \
        sixteen_adat_frames[0:256] + \
        [0] * 64 + \
        sixteen_adat_frames[256:]

    testdata_nrzi = encode_nrzi(testdata)

    print(f"FPGA clock freq: {clk_freq}")
    print(f"ADAT clock freq: {adat_freq}")
    print(f"FPGA/ADAT freq: {clockratio}")

    no_cycles = 10

    def sync_process():
        for _ in range(int(clockratio) * no_cycles):
            yield Tick("sync")

    def adat_process():
        for bit in testdata_nrzi: #[224:512 * 2]:
            yield dut.adat_in.eq(bit)
            yield Tick("adat")

    sim.add_sync_process(sync_process, domain="sync")
    sim.add_sync_process(adat_process, domain="adat")
    with sim.write_vcd(f'receiver-smoke-test-{str(samplerate)}.vcd'):
        sim.run()

if __name__ == "__main__":
    test_with_samplerate(48000)
    test_with_samplerate(44100)
