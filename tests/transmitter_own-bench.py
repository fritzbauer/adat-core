#!/usr/bin/env python3
#
# Copyright (c) 2021 Hans Baier <hansfbaier@gmail.com>
# SPDX-License-Identifier: CERN-OHL-W-2.0
#
import sys
sys.path.append('.')

from amaranth.sim import Simulator, Tick

from adat.transmitter_own import ADATTransmitterOwn
from adat.nrzidecoder import NRZIDecoder
from testdata import *

def test_with_samplerate(samplerate: int=48000):
    clk_freq = 50e6
    dut = ADATTransmitterOwn()
    adat_freq = NRZIDecoder.adat_freq(samplerate)
    clockratio = clk_freq / adat_freq

    print(f"FPGA clock freq: {clk_freq}")
    print(f"ADAT clock freq: {adat_freq}")
    print(f"FPGA/ADAT freq: {clockratio}")

    sim = Simulator(dut)
    sim.add_clock(1.0/clk_freq, domain="sync")
    sim.add_clock(1.0/adat_freq, domain="adat")

    def write(addr: int, sample: int, last: bool = False, drop_valid: bool = False):
        print("write {} {} {}".format(addr, sample, last))
        if last:
            yield dut.last_in.eq(1)
        print("last in set")
        yield dut.addr_in.eq(addr)
        print("addr in set")
        yield dut.sample_in.eq(sample)
        print("sample in set")
        yield dut.valid_in.eq(1)
        print("valid in set")
        yield Tick("sync")
        print("ticked")
        if drop_valid:
            yield dut.valid_in.eq(0)
        print("dropped valid")
        if last:
            yield dut.last_in.eq(0)
            yield Tick("sync")



    def wait(n_cycles: int):
        for _ in range(int(clockratio) * n_cycles):
            yield Tick("sync")

    def sync_process():
        yield Tick("sync")
        yield Tick("sync")
        #yield dut.user_data_in.eq(0xf)
        yield dut.user_data_in.eq(0b1010)
        for i in range(4):
            yield from write(i, i, drop_valid=True)
        for i in range(4):
            yield from write(4 + i, 0xc + i, i == 3, drop_valid=True)
        yield from wait(30)
        yield dut.user_data_in.eq(0xa)
        yield Tick("sync")
        for i in range(8):
            yield from write(i, (i + 1) << 4, i == 7)
        yield dut.user_data_in.eq(0xb)
        yield Tick("sync")
        for i in range(8):
            yield from write(i, (i + 1) << 8, i == 7)
        yield dut.user_data_in.eq(0xc)
        yield Tick("sync")
        for i in range(8):
            yield from write(i, (i + 1) << 12, i == 7)
        yield dut.user_data_in.eq(0xd)
        yield Tick("sync")
        for i in range(8):
            yield from write(i, (i + 1) << 16, i == 7)
        yield dut.user_data_in.eq(0xe)
        yield Tick("sync")
        for i in range(8):
            yield from write(i, (i + 1) << 20, i == 7)
        yield from wait(900)

    def adat_process():
        nrzi = []
        i = 0
        while i < 1600:
            yield Tick("adat")
            out = yield dut.adat_out
            nrzi.append(out)
            i += 1

        # skip initial zeros
        nrzi = nrzi[nrzi.index(1):]
        signal = decode_nrzi(nrzi)[1:]
        decoded = adat_decode(signal)
        print(decoded)
        user_bits = [frame[0] for frame in decoded]
        assert user_bits == [0xf, 0xa, 0xb, 0xc, 0xd]
        assert decoded[0][1:] == [0, 1, 2, 3, 0xc, 0xd, 0xe, 0xf]
        assert decoded[1][1:] == [0x10, 0x20, 0x30, 0x40, 0x50, 0x60, 0x70, 0x80]
        assert decoded[2][1:] == [0x100, 0x200, 0x300, 0x400, 0x500, 0x600, 0x700, 0x800]
        assert decoded[3][1:] == [0x1000, 0x2000, 0x3000, 0x4000, 0x5000, 0x6000, 0x7000, 0x8000]
        assert decoded[4][1:] == [0x10000, 0x20000, 0x30000, 0x40000, 0x50000, 0x60000, 0x70000, 0x80000]

    sim.add_sync_process(sync_process, domain="sync")
    sim.add_sync_process(adat_process, domain="adat")

    with sim.write_vcd(f'transmitter_own-smoke-test-{str(samplerate)}.vcd'):
        sim.run()
        #sim.run_until(100e-6, run_passive=True)

if __name__ == "__main__":
    test_with_samplerate(48000)